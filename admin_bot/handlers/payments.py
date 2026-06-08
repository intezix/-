from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from admin_bot.app_context import AppContext
from admin_bot.keyboards.inline import InlineKeyboards


router = Router()
kb = InlineKeyboards()


@router.message(Command("payments"))
async def cmd_payments(message: Message, ctx: AppContext) -> None:
    await ctx.roles.require_access(message.from_user.id)
    await message.answer("💳 <b>Платежи</b>\n\nВыберите фильтр.", reply_markup=kb.payments_filters())


@router.callback_query(lambda c: c.data and c.data.startswith("pay:list:"))
async def pay_list(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)

    parts = (callback.data or "").split(":", 3)
    status = parts[2] if len(parts) > 2 else "all"
    period = parts[3] if len(parts) > 3 else "24h"
    status_norm = None if status in ("all", "recurring") else status

    payments = await ctx.payments.list_payments(
        actor_telegram_user_id=callback.from_user.id,
        status=status_norm,
        period=period,
    )

    if not payments:
        await callback.message.edit_text(
            "💳 <b>Платежи</b>\n\nНичего не найдено.",
            reply_markup=kb.payments_filters(),
        )
        await callback.answer()
        return

    lines = ["💳 <b>Платежи</b>", ""]
    _STATUS_ICON = {"succeeded": "✅", "pending": "🕒", "canceled": "❌", "failed": "❌"}
    for p in payments[:20]:
        pid = str(p.get("payment_id") or "")
        tg_id = int(p.get("telegram_user_id") or 0)
        amount = str(p.get("amount") or "")
        currency = str(p.get("currency") or "")
        status_txt = str(p.get("status") or "")
        dt = p.get("created_at")
        date_str = dt.astimezone().strftime("%m-%d %H:%M") if dt else "—"
        icon = _STATUS_ICON.get(status_txt, "💳")
        lines.append(
            f"{icon} {date_str} · <b>{amount} {currency}</b> · "
            f"<code>{tg_id}</code> · <code>{pid[:18]}…</code>"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=kb.payment_list_keyboard(payments),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("pay:open:"))
async def pay_open(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    payment_id = (callback.data or "").split(":", 2)[2]
    role = await ctx.roles.require_access(callback.from_user.id)
    allow_raw = ctx.roles.can_view_raw_payments(role)
    try:
        text, row = await ctx.payments.get_payment_card(
            actor_telegram_user_id=callback.from_user.id,
            payment_id=payment_id,
        )
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    tg_id = int(row.get("telegram_user_id") or 0)
    await callback.message.edit_text(
        text,
        reply_markup=kb.payment_card(payment_id, tg_id, allow_raw=allow_raw),
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("pay:raw:"))
async def pay_raw(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    payment_id = (callback.data or "").split(":", 2)[2]
    try:
        raw = await ctx.payments.get_raw_payment_json(
            actor_telegram_user_id=callback.from_user.id,
            payment_id=payment_id,
        )
    except (PermissionError, ValueError) as e:
        await callback.answer(str(e), show_alert=True)
        return
    await callback.message.edit_text(
        "🧾 <b>Raw JSON</b>\n\n" + raw,
        reply_markup=kb.back_and_menu("nav:payments"),
    )
    await callback.answer()
