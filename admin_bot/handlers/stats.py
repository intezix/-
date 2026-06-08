from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from admin_bot.app_context import AppContext
from admin_bot.keyboards.inline import InlineKeyboards


router = Router()
kb = InlineKeyboards()


async def _send_stats(target: Message | CallbackQuery, *, ctx: AppContext, period: str) -> None:
    actor_id = target.from_user.id
    text = await ctx.stats.build_stats(actor_telegram_user_id=actor_id, period=period)
    markup = kb.back_and_menu("nav:stats")
    if isinstance(target, Message):
        await target.answer(text, reply_markup=markup)
    else:
        await target.message.edit_text(text, reply_markup=markup)
        await target.answer()


@router.message(Command("stats"))
async def cmd_stats(message: Message, ctx: AppContext) -> None:
    await ctx.roles.require_access(message.from_user.id)
    parts = (message.text or "").split(maxsplit=1)
    period = (parts[1].strip() if len(parts) > 1 else "today").lower()
    if period not in {"today", "7d", "30d", "all"}:
        await message.answer("Период: today | 7d | 30d | all", reply_markup=kb.to_menu())
        return
    await _send_stats(message, ctx=ctx, period=period)


@router.callback_query(lambda c: c.data and c.data.startswith("stats:period:"))
async def stats_period(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    period = (callback.data or "").split(":")[2].strip().lower()
    if period not in {"today", "7d", "30d", "all"}:
        await callback.answer("Неизвестный период", show_alert=False)
        return
    await _send_stats(callback, ctx=ctx, period=period)

