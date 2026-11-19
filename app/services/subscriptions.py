from app.database.db import Database
from app.integrations.hiddify import HiddifyAdapter


class Subscriptions:
    def __init__(self, db: Database, adapter: HiddifyAdapter):
        self.db = db
        self.adapter = adapter

    async def owned(self, user_id: int, subscription_id: int):
        async with self.db.connect() as conn:
            rows = await conn.execute_fetchall(
                """SELECT s.*, o.config_name FROM subscriptions s
                   JOIN orders o ON s.order_id=o.id WHERE s.id=? AND o.user_id=?""",
                (subscription_id, user_id),
            )
        return rows[0] if rows else None
