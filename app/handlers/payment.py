from aiogram import F, Router
from aiogram.types import Message

from app.config import Settings
from app.handlers.text import RECEIPT_REGISTERED
from app.services.orders import Orders

router = Router()


@router.message(F.photo)
async def receipt(message: Message, orders: Orders, settings: Settings):
    if not settings.can_test_payment(message.from_user.id):
        await message.answer("ارسال رسید فعلاً در دسترس نیست.")
        return
    photo = message.photo[-1]
    result = await orders.receipt(
        message.from_user.id, message.from_user.username,
        photo.file_id, photo.file_unique_id, photo.file_size,
    )
    await message.answer({
        "registered": RECEIPT_REGISTERED,
        "invalid": "اندازهٔ عکس معتبر نیست. لطفاً عکسی با اندازهٔ حداکثر ۱۰ مگابایت بفرستید.",
        "inactive": "ابتدا در سفارش خود دکمهٔ «پرداخت کردم، ارسال رسید» را بزنید.",
        "duplicate": "این تصویر رسید قبلاً ثبت شده است. عکس دیگری بفرستید.",
    }[result])


@router.message(F.document)
async def document(message: Message):
    await message.answer("برای ارسال رسید، تصویر را به‌صورت عکس بفرستید.")
