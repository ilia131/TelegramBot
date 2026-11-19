from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup,
)

BUY = "خرید اشتراک"
MANAGE = "مدیریت اشتراک خریداری‌شده"
WALLET = "کیف پول ربات"
HELP = "راهنما"
SUPPORT = "پشتیبانی"
BACK = "بازگشت"
CANCEL = "لغو سفارش"


def inline(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=data) for label, data in row]
        for row in rows
    ])


MAIN = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=t) for t in row]
              for row in ((BUY,), (MANAGE,), (WALLET,), (HELP, SUPPORT))],
    resize_keyboard=True,
)


def review(order_id: int):
    return inline([
        ("تأیید پرداخت", f"admin:approved:{order_id}"),
        ("رد پرداخت", f"admin:rejected:{order_id}"),
    ])
