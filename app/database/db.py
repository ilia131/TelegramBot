from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from app.plans import PLANS


class Database:
    def __init__(self, path: Path):
        self.path = path

    @asynccontextmanager
    async def connect(self):
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON")
            yield conn

    @asynccontextmanager
    async def transaction(self):
        async with self.connect() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                await conn.commit()
            except BaseException:
                await conn.rollback()
                raise

    async def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self.connect() as conn:
            await conn.execute("PRAGMA journal_mode = WAL")
            await conn.executescript(Path(__file__).with_name("schema.sql").read_text())
            await conn.executemany(
                """INSERT INTO plans(id, volume_gb, duration_days, price_toman)
                   VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET
                   volume_gb=excluded.volume_gb, duration_days=excluded.duration_days,
                   price_toman=excluded.price_toman""",
                [(p.gb, p.gb, p.days, p.price) for p in PLANS.values()],
            )
            await conn.commit()
