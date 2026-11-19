import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from aiogram import Bot
from aiogram.methods import SendMessage, SendPhoto
from aiogram.types import Update

from app.config import Settings
from app.database.db import Database
from app.database.models import OrderStatus as Status
from app.handlers.text import NAME_ORDER, NAME_PROMPT, RECEIPT_REGISTERED
from app.integrations.hiddify import HiddifyAdapter
from app.main import dispatcher
from app.services.notifications import Notifications
from app.services.orders import Orders
from app.services.subscriptions import Subscriptions
from app.utils.validation import MAX_RECEIPT_BYTES


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Database(Path(temp.name) / "bot.db")
        await self.db.initialize()
        self.orders = Orders(self.db, frozenset({101, 102}))

    async def pending(self, user=11, receipt="unique"):
        order = await self.orders.select(user, "test_user", 10)
        await self.orders.transition(user, order["id"], "direct")
        await self.orders.transition(user, order["id"], "paid")
        self.assertEqual(
            await self.orders.receipt(user, "test_user", "file", receipt, 1024), "registered",
        )
        return order["id"]

    async def test_database_plans_and_wallet_constraints(self):
        async with self.db.connect() as conn:
            rows = await conn.execute_fetchall(
                "SELECT volume_gb,duration_days,price_toman FROM plans ORDER BY volume_gb",
            )
            self.assertEqual([tuple(row) for row in rows], [
                (10, 30, 120000), (20, 30, 230000), (30, 30, 340000),
                (40, 30, 450000), (50, 30, 560000), (80, 30, 880000), (120, 30, 1260000),
            ])
        self.assertIsNone(await self.orders.select(11, None, 99))
        await self.orders.select(11, None, 10)
        self.assertEqual(await self.orders.wallet_balance(11), 0)
        with self.assertRaises(sqlite3.IntegrityError):
            async with self.db.transaction() as conn:
                await conn.execute("UPDATE wallets SET balance_toman=-1 WHERE user_id=?", (11,))
        async with self.db.transaction() as conn:
            await conn.execute(
                "INSERT INTO wallet_transactions(user_id,idempotency_key,amount_toman) VALUES (?,?,?)",
                (11, "sample", 20),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            async with self.db.transaction() as conn:
                await conn.execute(
                    "INSERT INTO wallet_transactions(user_id,idempotency_key,amount_toman) VALUES (?,?,?)",
                    (11, "sample", 20),
                )

    async def test_receipt_gates_and_cancellation(self):
        plan = await self.orders.select(11, None, 20)
        order_id = plan["id"]
        self.assertEqual(plan["price_toman"], 230000)
        self.assertEqual((await self.orders.select(11, None, 20))["id"], order_id)
        self.assertIsNone(await self.orders.transition(12, order_id, "direct"))
        await self.orders.transition(11, order_id, "direct")
        self.assertEqual(await self.orders.receipt(11, None, "file", "x", 42), "inactive")
        await self.orders.transition(11, order_id, "paid")
        self.assertEqual(await self.orders.receipt(11, None, "file", "x", None), "invalid")
        self.assertEqual(
            await self.orders.receipt(11, None, "file", "x", MAX_RECEIPT_BYTES + 1), "invalid",
        )
        self.assertEqual(await self.orders.receipt(11, None, "file", "x", 42), "registered")
        self.assertIsNone(await self.orders.transition(11, order_id, "cancel"))
        other = await self.orders.select(11, None, 30)
        await self.orders.transition(11, other["id"], "direct")
        await self.orders.transition(11, other["id"], "paid")
        self.assertEqual(await self.orders.receipt(11, None, "file", "x", 42), "duplicate")
        self.assertEqual((await self.orders.transition(11, other["id"], "cancel"))["status"], Status.CANCELLED)

    async def test_admin_authorization_and_competing_decisions(self):
        order_id = await self.pending()
        self.assertFalse(await self.orders.decide(11, order_id, Status.APPROVED))
        outcomes = await asyncio.gather(
            self.orders.decide(101, order_id, Status.APPROVED),
            self.orders.decide(102, order_id, Status.REJECTED),
        )
        self.assertEqual(outcomes.count(True), 1)
        async with self.db.connect() as conn:
            actions = await conn.execute_fetchall("SELECT * FROM admin_actions")
        self.assertEqual(len(actions), 1)

    async def test_approval_persists_through_restart(self):
        order_id = await self.pending()
        self.assertTrue(await self.orders.decide(101, order_id, Status.APPROVED))
        reopened = Database(self.db.path)
        await reopened.initialize()
        orders = Orders(reopened, self.orders.admin_ids)
        self.assertTrue(await orders.approved(11, order_id))
        self.assertFalse(await orders.save_name(12, order_id, "کانفیگ"))
        self.assertFalse(await orders.save_name(11, order_id, "<bad>"))
        self.assertTrue(await orders.save_name(11, order_id, "کانفیگ‌ خانه"))
        self.assertFalse(await orders.save_name(11, order_id, "تکراری"))
        row = (await orders.history(11, 100))[0]
        self.assertEqual(row["status"], Status.AWAITING_PROVISIONING)
        self.assertIsNone(row["subscription_id"])
        with self.assertRaises(NotImplementedError):
            await HiddifyAdapter().create_user(order_id=order_id, name="test", quota_gb=10, duration_days=30)

    async def test_reject_and_notify_after_restart(self):
        order_id = await self.pending()
        self.assertTrue(await self.orders.decide(101, order_id, Status.REJECTED))
        self.assertFalse(await self.orders.decide(101, order_id, Status.APPROVED))
        fake_bot = AsyncMock()
        queue = Notifications(Database(self.db.path), fake_bot, self.orders.admin_ids)
        await queue.process()
        await queue.process()
        fake_bot.send_photo.assert_not_awaited()
        fake_bot.send_message.assert_awaited_once()
        self.assertIn("رد شد", fake_bot.send_message.await_args.args[1])
        self.assertNotEqual((await self.orders.select(11, None, 20))["id"], order_id)

    async def test_telegram_dispatch_receipt_approval_and_name(self):
        bot = Bot("900:synthetic")
        self.addAsyncCleanup(bot.session.close)
        bot.session.make_request = AsyncMock(return_value=True)
        dp = dispatcher()
        settings = Settings("900:synthetic", self.orders.admin_ids, "0000000000000000",
                            "دارندهٔ کارت آزمایشی", self.db.path, True)
        subscription_service = Subscriptions(self.db, HiddifyAdapter())
        user = {"id": 101, "is_bot": False, "first_name": "مدیر"}
        bot_user = {"id": 900, "is_bot": True, "first_name": "ربات"}
        chat = {"id": 101, "type": "private"}
        timestamp = 1795100000

        async def feed(kind, data):
            update = Update.model_validate({"update_id": 1, kind: data}, context={"bot": bot})
            await dp.feed_update(bot, update, orders=self.orders, settings=settings,
                                 subscriptions=subscription_service)

        async def callback(data):
            await feed("callback_query", {
                "id": "synthetic", "from": user, "chat_instance": "private", "data": data,
                "message": {"message_id": 5, "date": timestamp, "chat": chat, "from": bot_user,
                            "text": "گزینه"},
            })

        async def text_message(**fields):
            await feed("message", {
                "message_id": 6, "date": timestamp, "chat": chat, "from": user, **fields,
            })

        await text_message(text="/start")
        await callback("buy:server")
        await callback("plan:10")
        await callback("order:direct:1")
        await callback("order:paid:1")
        await text_message(photo=[{
            "file_id": "file", "file_unique_id": "unique", "width": 20, "height": 20, "file_size": 42,
        }])
        methods = [entry.args[1] for entry in bot.session.make_request.await_args_list]
        self.assertTrue(any(isinstance(m, SendMessage) and m.text == RECEIPT_REGISTERED for m in methods))
        queue = Notifications(self.db, bot, self.orders.admin_ids)
        await queue.process()
        methods = [entry.args[1] for entry in bot.session.make_request.await_args_list]
        self.assertEqual(sum(isinstance(m, SendPhoto) for m in methods), 2)
        await callback("admin:approved:1")
        await queue.process()
        await text_message(text="خانه", reply_to_message={
            "message_id": 7, "date": timestamp, "chat": chat, "from": bot_user,
            "text": f"{NAME_PROMPT}\n{NAME_ORDER}1",
        })
        self.assertEqual((await self.orders.history(101, 10))[0]["config_name"], "خانه")
