from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.config import Settings
from app.database.models import OrderStatus as Status
from app.handlers.text import EXPIRED
from app.services.orders import Orders

router = Router()


@router.callback_query(F.data.regexp(r"^admin:(approved|rejected):[0-9]{1,18}$"))
async def decide(query: CallbackQuery, orders: Orders, settings: Settings):
    if query.from_user.id not in settings.admin_ids:
        await query.answer("شما اجازهٔ بررسی پرداخت‌ها را ندارید.", show_alert=True)
        return
    _, decision, order_id = query.data.split(":")
    if not await orders.decide(query.from_user.id, int(order_id), Status(decision)):
        await query.answer(EXPIRED)
        return
    await query.answer("تصمیم شما ثبت شد.")
    await query.message.edit_reply_markup(reply_markup=None)
