from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.config import Settings
from app.handlers.text import WALLET_INACTIVE
from app.keyboards.menus import HELP, MAIN, SUPPORT, WALLET

router = Router()


@router.message(CommandStart())
async def start(message: Message):
    await message.answer("خوش آمدید. یک گزینه را از منوی زیر انتخاب کنید.", reply_markup=MAIN)


@router.message(F.text == WALLET)
async def wallet(message: Message):
    await message.answer(WALLET_INACTIVE)


@router.message(F.text == HELP)
async def help_menu(message: Message):
    await message.answer(
        "از منوی «خرید اشتراک» می‌توانید پلن‌ها را مشاهده کنید. "
        "پیگیری سفارش و انتخاب نام کانفیگ از بخش «مدیریت اشتراک خریداری‌شده» انجام می‌شود. "
        "پرداخت عمومی، کیف پول و تحویل خودکار اشتراک فعلاً غیرفعال هستند."
    )


@router.message(F.text == SUPPORT)
async def support(message: Message, settings: Settings):
    if settings.support_username:
        await message.answer(f"برای ارتباط با پشتیبانی به @{settings.support_username} پیام بدهید.")
    else:
        await message.answer("راه ارتباط با پشتیبانی هنوز تنظیم نشده است.")


@router.message(F.text == "/myid")
async def my_id(message: Message):
    await message.answer(f"شناسهٔ عددی تلگرام شما: {message.from_user.id}")
