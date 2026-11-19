from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.database.models import OrderStatus as Status
from app.handlers.text import EXPIRED, WALLET_INACTIVE
from app.keyboards.menus import BACK, BUY, CANCEL, inline
from app.plans import PLANS, SERVER
from app.services.orders import Orders
from app.utils.formatting import details, number

router = Router()
PAYMENTS_INACTIVE = "پرداخت مستقیم فعلاً غیرفعال است. لطفاً وجهی واریز نکنید."


@router.message(F.text == BUY)
async def buy(message: Message):
    await message.answer("سرور مورد نظر را انتخاب کنید.", reply_markup=inline(
        [(SERVER, "buy:server")], [(BACK, "buy:home")],
    ))


@router.callback_query(F.data == "buy:home")
async def home(query: CallbackQuery):
    await query.answer()
    await query.message.edit_text("برای ادامه از منوی اصلی استفاده کنید.")


@router.callback_query(F.data == "buy:server")
async def list_plans(query: CallbackQuery, orders: Orders, settings: Settings):
    await query.answer()
    async with orders.db.connect() as conn:
        current = await orders.open_order(conn, query.from_user.id)
    if current:
        await show_order(query.message, current, orders, settings)
        return
    await show_plans(query.message)


async def show_plans(message: Message):
    rows = [
        [(f"{number(plan.gb)} گیگابایت · {number(plan.price)} تومان", f"plan:{plan.gb}")]
        for plan in PLANS.values()
    ]
    await message.edit_text(
        f"پلن‌های {SERVER}\nمدت اعتبار همهٔ پلن‌ها ۳۰ روز است.",
        reply_markup=inline(*rows, [(BACK, "buy:servers")]),
    )


@router.callback_query(F.data == "buy:servers")
async def servers(query: CallbackQuery):
    await query.answer()
    await query.message.edit_text("سرور مورد نظر را انتخاب کنید.", reply_markup=inline(
        [(SERVER, "buy:server")], [(BACK, "buy:home")],
    ))


@router.callback_query(F.data.regexp(r"^plan:[0-9]{1,6}$"))
async def choose(query: CallbackQuery, orders: Orders, settings: Settings):
    order = await orders.select(
        query.from_user.id, query.from_user.username, int(query.data.split(":")[1]),
    )
    if not order:
        await query.answer(EXPIRED)
        return
    await query.answer()
    await show_order(query.message, order, orders, settings)


async def show_order(message: Message, order, orders: Orders, settings: Settings):
    order_id = order["id"]
    can_pay = settings.can_test_payment(order["user_id"])
    if order["status"] == Status.AWAITING_RECEIPT and can_pay:
        await message.edit_text(
            "لطفاً تصویر رسید آزمایشی را به‌صورت عکس در همین گفتگو بفرستید. "
            "حداکثر اندازهٔ عکس ۱۰ مگابایت است.",
            reply_markup=inline(
                [(BACK, f"order:transfer:{order_id}")],
                [(CANCEL, f"order:cancel:{order_id}")],
            ),
        )
        return
    if order["status"] == Status.AWAITING_TRANSFER and can_pay:
        card = " ".join(settings.card_number[i:i + 4] for i in range(0, 16, 4))
        amount = order["price_toman"]
        await message.edit_text(
            "حالت آزمایشی مدیران. برای اجرای واقعی، مبلغ زیر باید کارت‌به‌کارت شود. "
            "لطفاً وجهی واریز نکنید و فقط از رسید ساختگی استفاده کنید.\n\n"
            f"مبلغ: {number(amount)} تومان (معادل {number(amount * 10)} ریال)\n"
            f"شماره کارت: {card}\nدارندهٔ کارت: {settings.card_holder}\n\n"
            "پس از شبیه‌سازی انتقال، دکمهٔ ارسال رسید را بزنید.",
            reply_markup=inline(
                [("پرداخت کردم، ارسال رسید", f"order:paid:{order_id}")],
                [(BACK, f"order:confirm:{order_id}")],
                [(CANCEL, f"order:cancel:{order_id}")],
            ),
        )
        return
    balance = await orders.wallet_balance(order["user_id"])
    await message.edit_text(
        f"{details(order)}\nموجودی کیف پول: {number(balance)} تومان\n"
        "توضیحات: این پلن تک‌کاربره است.",
        reply_markup=inline(
            [("پرداخت مستقیم (کارت به کارت)", f"order:direct:{order_id}")],
            [("پرداخت از کیف پول ربات", "buy:wallet")],
            [(BACK, f"order:cancel:{order_id}")],
        ),
    )


@router.callback_query(F.data == "buy:wallet")
async def disabled_wallet(query: CallbackQuery):
    await query.answer(WALLET_INACTIVE, show_alert=True)


@router.callback_query(F.data.regexp(r"^order:(direct|paid|transfer|confirm|cancel):[0-9]{1,18}$"))
async def order_action(query: CallbackQuery, orders: Orders, settings: Settings):
    _, action, order_id = query.data.split(":")
    if action != "cancel" and not settings.can_test_payment(query.from_user.id):
        await query.answer(PAYMENTS_INACTIVE, show_alert=True)
        return
    order = await orders.transition(query.from_user.id, int(order_id), action)
    if not order:
        await query.answer(EXPIRED)
        return
    await query.answer()
    if action == "cancel":
        await show_plans(query.message)
        return
    await show_order(query.message, order, orders, settings)
