import asyncio
import logging
import time

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from app.database.db import Database
from app.handlers.subscriptions import ask_name
from app.keyboards.menus import MAIN, review
from app.plans import SERVER
from app.utils.formatting import details, number

logger = logging.getLogger(__name__)


class Notifications:
    def __init__(self, db: Database, bot: Bot, admin_ids: frozenset[int]):
        self.db = db
        self.bot = bot
        self.admin_ids = admin_ids

    async def pending(self):
        async with self.db.connect() as conn:
            return await conn.execute_fetchall(
                """SELECT n.*, o.user_id, o.volume_gb, o.duration_days, o.price_toman,
                          o.status, u.username, r.file_id
                   FROM notifications n JOIN orders o ON n.order_id=o.id
                   JOIN users u ON o.user_id=u.id
                   LEFT JOIN payment_receipts r ON o.id=r.order_id
                   WHERE n.finished_at IS NULL AND n.next_attempt <= ?
                   ORDER BY n.id LIMIT 20""",
                (int(time.time()),),
            )

    async def finish(self, notification_id: int):
        async with self.db.transaction() as conn:
            await conn.execute(
                "UPDATE notifications SET finished_at=CURRENT_TIMESTAMP WHERE id=?",
                (notification_id,),
            )

    async def retry(self, notification, delay: int):
        async with self.db.transaction() as conn:
            await conn.execute(
                "UPDATE notifications SET attempts=attempts+1, next_attempt=? WHERE id=?",
                (int(time.time()) + delay, notification["id"]),
            )

    async def send(self, row):
        recipient = row["recipient"]
        order_id = row["order_id"]
        if row["kind"] == "review":
            if row["status"] != "pending_review" or recipient not in self.admin_ids:
                return
            username = f"@{row['username']}" if row["username"] else "ثبت نشده"
            await self.bot.send_photo(
                recipient, row["file_id"],
                caption=(
                    f"رسید آزمایشی · سفارش {number(order_id)}\n"
                    f"شناسهٔ تلگرام: {row['user_id']}\nنام کاربری: {username}\n"
                    f"پلن: {SERVER} · {number(row['volume_gb'])} گیگابایت\n{details(row)}"
                ),
                reply_markup=review(order_id),
            )
        elif row["kind"] == "approved" and row["status"] == "approved":
            await self.bot.send_message(
                recipient, f"پرداخت آزمایشی سفارش {number(order_id)} تأیید شد.",
            )
            await ask_name(self.bot, recipient, order_id)
        elif row["kind"] == "rejected":
            await self.bot.send_message(
                recipient, f"پرداخت آزمایشی سفارش {number(order_id)} رد شد. "
                "برای سفارش دیگری گزینهٔ «خرید اشتراک» را انتخاب کنید.",
                reply_markup=MAIN,
            )

    async def process(self):
        for row in await self.pending():
            try:
                await self.send(row)
            except (TelegramBadRequest, TelegramForbiddenError) as exc:
                logger.warning("ارسال اعلان %d متوقف شد (%s).", row["id"], type(exc).__name__)
            except TelegramRetryAfter as exc:
                await self.retry(row, exc.retry_after + 1)
                continue
            except Exception as exc:
                logger.warning("ارسال اعلان %d ناموفق بود (%s).", row["id"], type(exc).__name__)
                await self.retry(row, min(600, 5 * 2 ** min(row["attempts"], 7)))
                continue
            await self.finish(row["id"])

    async def run(self):
        while True:
            try:
                await self.process()
            except Exception as exc:
                logger.warning("پردازش اعلان‌ها ناموفق بود (%s).", type(exc).__name__)
            await asyncio.sleep(2)
