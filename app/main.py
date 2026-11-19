import asyncio
import logging
import os
from contextlib import suppress

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent, Message

from app.config import Settings
from app.database.db import Database
from app.handlers import admin, payment, purchase, start, subscriptions
from app.integrations.hiddify import HiddifyAdapter
from app.services.notifications import Notifications
from app.services.orders import Orders
from app.services.subscriptions import Subscriptions

logger = logging.getLogger(__name__)


def dispatcher() -> Dispatcher:
    dp = Dispatcher(disable_fsm=True)
    dp.message.filter(F.chat.type == "private", F.from_user)
    dp.callback_query.filter(F.message.func(
        lambda message: isinstance(message, Message) and message.chat.type == "private",
    ))
    dp.include_routers(subscriptions.router, start.router, purchase.router, admin.router, payment.router)

    @dp.errors()
    async def handle_error(event: ErrorEvent):
        exc = event.exception
        if isinstance(exc, TelegramBadRequest) and "message is not modified" in exc.message.lower():
            return True
        logger.error("پردازش پیام ناموفق بود (%s).", type(exc).__name__)
        with suppress(Exception):
            if event.update.callback_query:
                await event.update.callback_query.answer("خطایی رخ داد. دوباره تلاش کنید.")
            elif event.update.message:
                await event.update.message.answer("خطایی رخ داد. دوباره تلاش کنید.")
        return True

    return dp


async def run(settings: Settings):
    db = Database(settings.database_path)
    await db.initialize()
    dp = dispatcher()
    async with Bot(settings.token, session=AiohttpSession(timeout=12)) as bot:
        await bot.delete_webhook(drop_pending_updates=False)
        worker = asyncio.create_task(Notifications(db, bot, settings.admin_ids).run())
        try:
            logger.info("ربات آمادهٔ دریافت پیام‌هاست.")
            await dp.start_polling(
                bot, handle_as_tasks=False, close_bot_session=False,
                allowed_updates=dp.resolve_used_update_types(),
                settings=settings,
                orders=Orders(db, settings.admin_ids),
                subscriptions=Subscriptions(db, HiddifyAdapter()),
            )
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker


def main():
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Third-party exceptions may include request URLs or credentials.
    logging.getLogger("aiogram").setLevel(logging.CRITICAL + 1)
    logging.getLogger("aiohttp").setLevel(logging.CRITICAL + 1)
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from None
    try:
        asyncio.run(run(settings))
    except KeyboardInterrupt:
        return
    except Exception as exc:
        logger.error("راه‌اندازی یا اجرای ربات ناموفق بود (%s).", type(exc).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
