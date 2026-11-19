import aiosqlite

from app.database.db import Database
from app.database.models import OrderStatus as Status
from app.plans import PLANS
from app.utils.validation import MAX_RECEIPT_BYTES, valid_name


class Orders:
    def __init__(self, db: Database, admin_ids: frozenset[int]):
        self.db = db
        self.admin_ids = admin_ids

    async def select(self, user_id: int, username: str | None, plan_id: int):
        plan = PLANS.get(plan_id)
        if plan is None:
            return None
        async with self.db.transaction() as conn:
            await conn.execute(
                """INSERT INTO users(id, username) VALUES (?, ?)
                   ON CONFLICT(id) DO UPDATE SET username=excluded.username""",
                (user_id, username),
            )
            await conn.execute("INSERT OR IGNORE INTO wallets(user_id) VALUES (?)", (user_id,))
            current = await self.open_order(conn, user_id)
            if current:
                return current
            rows = await conn.execute_fetchall(
                """INSERT INTO orders(user_id, plan_id, volume_gb, duration_days, price_toman, status)
                   VALUES (?, ?, ?, ?, ?, ?) RETURNING *""",
                (user_id, plan_id, plan.gb, plan.days, plan.price, Status.DRAFT),
            )
            return rows[0]

    @staticmethod
    async def open_order(conn, user_id: int):
        rows = await conn.execute_fetchall(
            """SELECT * FROM orders WHERE user_id = ?
               AND status IN ('draft', 'awaiting_transfer', 'awaiting_receipt')""",
            (user_id,),
        )
        return rows[0] if rows else None

    async def wallet_balance(self, user_id: int) -> int:
        async with self.db.connect() as conn:
            rows = await conn.execute_fetchall(
                "SELECT balance_toman FROM wallets WHERE user_id=?", (user_id,),
            )
            return rows[0][0] if rows else 0

    async def transition(self, user_id: int, order_id: int, action: str):
        previous, status = {
            "direct": ((Status.DRAFT,), Status.AWAITING_TRANSFER),
            "paid": ((Status.AWAITING_TRANSFER,), Status.AWAITING_RECEIPT),
            "transfer": ((Status.AWAITING_RECEIPT,), Status.AWAITING_TRANSFER),
            "confirm": ((Status.AWAITING_TRANSFER, Status.AWAITING_RECEIPT), Status.DRAFT),
            "cancel": ((Status.DRAFT, Status.AWAITING_TRANSFER, Status.AWAITING_RECEIPT),
                       Status.CANCELLED),
        }[action]
        placeholders = ", ".join("?" for _ in previous)
        async with self.db.transaction() as conn:
            rows = await conn.execute_fetchall(
                f"""UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=? AND user_id=? AND status IN ({placeholders}) RETURNING *""",
                (status, order_id, user_id, *previous),
            )
            return rows[0] if rows else None

    async def receipt(self, user_id: int, username: str | None, file_id: str,
                      unique_id: str, size: int | None) -> str:
        if not file_id or not unique_id or not size or not 0 < size <= MAX_RECEIPT_BYTES:
            return "invalid"
        try:
            async with self.db.transaction() as conn:
                order = await self.open_order(conn, user_id)
                if not order or order["status"] != Status.AWAITING_RECEIPT:
                    return "inactive"
                order_id = order["id"]
                await conn.execute(
                    """INSERT INTO payment_receipts(order_id,file_id,file_unique_id,file_size)
                       VALUES (?, ?, ?, ?)""",
                    (order_id, file_id, unique_id, size),
                )
                await conn.execute("UPDATE users SET username=? WHERE id=?", (username, user_id))
                await conn.execute(
                    "UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (Status.PENDING_REVIEW, order_id),
                )
                await conn.executemany(
                    "INSERT INTO notifications(order_id,recipient,kind) VALUES (?, ?, 'review')",
                    [(order_id, admin_id) for admin_id in self.admin_ids],
                )
        except aiosqlite.IntegrityError as exc:
            if exc.sqlite_errorname != "SQLITE_CONSTRAINT_UNIQUE":
                raise
            return "duplicate"
        return "registered"

    async def decide(self, admin_id: int, order_id: int, decision: Status):
        if admin_id not in self.admin_ids:
            return False
        if decision not in (Status.APPROVED, Status.REJECTED):
            raise ValueError("Unsupported decision")
        async with self.db.transaction() as conn:
            rows = await conn.execute_fetchall(
                """UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND status='pending_review' RETURNING user_id""",
                (decision, order_id),
            )
            if not rows:
                return False
            await conn.execute(
                "INSERT INTO admin_actions(order_id,admin_id,decision) VALUES (?, ?, ?)",
                (order_id, admin_id, decision),
            )
            await conn.execute(
                "INSERT INTO notifications(order_id,recipient,kind) VALUES (?, ?, ?)",
                (order_id, rows[0]["user_id"], decision),
            )
            return True

    async def approved(self, user_id: int, order_id: int):
        async with self.db.connect() as conn:
            return bool(await conn.execute_fetchall(
                "SELECT id FROM orders WHERE id=? AND user_id=? AND status='approved'",
                (order_id, user_id),
            ))

    async def save_name(self, user_id: int, order_id: int, name: str):
        if not valid_name(name):
            return False
        async with self.db.transaction() as conn:
            rows = await conn.execute_fetchall(
                """UPDATE orders SET config_name=?, status=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND user_id=? AND status='approved' RETURNING id""",
                (name, Status.AWAITING_PROVISIONING, order_id, user_id),
            )
            return bool(rows)

    async def history(self, user_id: int, before: int):
        async with self.db.connect() as conn:
            return await conn.execute_fetchall(
                """SELECT o.*, s.id AS subscription_id FROM orders o
                   LEFT JOIN subscriptions s ON s.order_id=o.id
                   WHERE o.user_id=? AND o.id<?
                   AND o.status IN ('pending_review','approved','awaiting_provisioning','provisioned')
                   ORDER BY o.id DESC LIMIT 11""",
                (user_id, before),
            )
