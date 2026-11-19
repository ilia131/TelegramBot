import os
import sqlite3
from pathlib import Path


def main():
    path = Path(os.getenv("DATABASE_PATH", "/app/data/bot.db")).resolve()
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2) as conn:
        conn.execute("SELECT id FROM orders LIMIT 1").fetchone()


if __name__ == "__main__":
    main()
