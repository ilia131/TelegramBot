from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, ForceReply, Message

from app.handlers.text import EXPIRED, INACTIVE, NAME_ORDER, NAME_PROMPT
from app.keyboards.menus import BACK, MANAGE, inline
from app.services.orders import Orders
from app.services.subscriptions import Subscriptions
from app.utils.formatting import number
from app.utils.validation import valid_name

router = Router()


async def ask_name(bot: Bot, user_id: int, order_id: int):
    await bot.send_message(
        user_id, f"{NAME_PROMPT}\n{NAME_ORDER}{order_id}",
        reply_markup=ForceReply(input_field_placeholder="نام کانفیگ"),
    )


async def show_history(message: Message, orders: Orders, before: int = 2**63 - 1):
    rows = await orders.history(message.chat.id, before)
    labels = {
        "pending_review": "در انتظار بررسی پرداخت",
        "approved": "در انتظار انتخاب نام",
        "awaiting_provisioning": "در انتظار فعال‌سازی",
        "provisioned": "اشتراک",
    }
    text = ["سفارش‌ها و اشتراک‌های شما"]
    buttons = []
    for row in rows[:10]:
        order_id = row["id"]
        text.append(
            f"سفارش {number(order_id)} · {number(row['volume_gb'])} گیگابایت · "
            f"{labels[row['status']]}"
        )
        if row["status"] == "approved":
            buttons.append([(f"انتخاب نام سفارش {number(order_id)}", f"name:{order_id}")])
        if row["subscription_id"] is not None:
            buttons.append([(f"اشتراک سفارش {number(order_id)}", f"sub:view:{row['subscription_id']}")])
    if not rows:
        text.append("سفارش در حال بررسی یا اشتراک فعالی پیدا نشد.")
    text.append(INACTIVE)
    if len(rows) > 10:
        buttons.append([("سفارش‌های قدیمی‌تر", f"history:{rows[9]['id']}")])
    buttons.append([(BACK, "buy:home")])
    await message.answer("\n".join(text), reply_markup=inline(*buttons))


@router.message(F.text == MANAGE)
async def manage(message: Message, orders: Orders):
    await show_history(message, orders)


@router.callback_query(F.data.regexp(r"^history:[0-9]{1,18}$"))
async def older(query: CallbackQuery, orders: Orders):
    await query.answer()
    await show_history(query.message, orders, int(query.data.split(":")[1]))


@router.callback_query(F.data.regexp(r"^name:[0-9]{1,18}$"))
async def request_name(query: CallbackQuery, bot: Bot, orders: Orders):
    order_id = int(query.data.split(":")[1])
    if not await orders.approved(query.from_user.id, order_id):
        await query.answer(EXPIRED)
        return
    await query.answer()
    await ask_name(bot, query.from_user.id, order_id)


@router.message(F.text, F.reply_to_message.text.startswith(NAME_PROMPT + "\n" + NAME_ORDER))
async def save_name(message: Message, bot: Bot, orders: Orders):
    prompt = message.reply_to_message
    if not prompt.from_user or prompt.from_user.id != bot.id:
        return
    raw_id = prompt.text.removeprefix(NAME_PROMPT + "\n" + NAME_ORDER)
    if not raw_id.isascii() or not raw_id.isdecimal() or len(raw_id) > 18:
        return
    order_id = int(raw_id)
    name = message.text.strip()
    if not valid_name(name):
        await message.answer("نام باید ۱ تا ۴۸ نویسه باشد. از حروف، عدد، فاصله، خط تیره یا زیرخط استفاده کنید.")
        return
    if not await orders.save_name(message.from_user.id, order_id, name):
        await message.answer(EXPIRED)
        return
    await message.answer(f"نام کانفیگ برای سفارش {number(order_id)} ثبت شد. {INACTIVE}")


@router.callback_query(F.data.regexp(r"^sub:(view|link|renew|refresh|disable):[0-9]{1,18}$"))
async def subscription_action(query: CallbackQuery, subscriptions: Subscriptions):
    _, action, subscription_id = query.data.split(":")
    record = await subscriptions.owned(query.from_user.id, int(subscription_id))
    if not record:
        await query.answer(EXPIRED)
        return
    if action != "view":
        await query.answer(INACTIVE, show_alert=True)
        return
    await query.answer()
    prefix = f"sub:{{}}:{subscription_id}"
    await query.message.answer(
        f"اشتراک «{record['config_name']}»\n{INACTIVE}",
        reply_markup=inline(
            [("دریافت لینک سابسکریپشن", prefix.format("link"))],
            [("تمدید اشتراک", prefix.format("renew"))],
            [("بروزرسانی اطلاعات", prefix.format("refresh"))],
            [("غیرفعال کردن", prefix.format("disable"))],
            [(BACK, "buy:home")],
        ),
    )
