import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)
    admin_ids: frozenset[int]
    card_number: str
    card_holder: str
    database_path: Path
    demo_payments: bool = False
    support_username: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        token = os.getenv("BOT_TOKEN", "")
        if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
            raise ValueError("مقدار BOT_TOKEN معتبر نیست.")
        raw_ids = os.getenv("ADMIN_IDS", "")
        if not re.fullmatch(r"[1-9][0-9]{0,15}(?:[ ,]+[1-9][0-9]{0,15})*", raw_ids.strip()):
            raise ValueError("شناسه‌های عددی مدیران را در ADMIN_IDS وارد کنید.")
        ids = frozenset(map(int, raw_ids.replace(",", " ").split()))
        demo_payments = os.getenv("DEMO_PAYMENTS", "false").lower() == "true"
        card = os.getenv("CARD_NUMBER", "").replace(" ", "")
        holder = os.getenv("CARD_HOLDER", "").strip()
        if (demo_payments or card or holder) and (
            not re.fullmatch(r"[0-9]{16}", card) or not 0 < len(holder) <= 100
        ):
            raise ValueError("مشخصات کارت بانکی معتبر نیست.")
        support = os.getenv("SUPPORT_USERNAME", "").strip().lstrip("@")
        if support and not re.fullmatch(r"[A-Za-z0-9_]{5,32}", support):
            raise ValueError("نام کاربری پشتیبانی معتبر نیست.")
        return cls(
            token, ids, card, holder,
            Path(os.getenv("DATABASE_PATH", "/app/data/bot.db")),
            demo_payments, support,
        )

    def can_test_payment(self, user_id: int) -> bool:
        return self.demo_payments and user_id in self.admin_ids
