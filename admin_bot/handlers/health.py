from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from admin_bot.app_context import AppContext
from admin_bot.keyboards.inline import InlineKeyboards


router = Router()
kb = InlineKeyboards()


async def _send_health(target: Message | CallbackQuery, *, ctx: AppContext) -> None:
    actor_id = target.from_user.id if isinstance(target, Message) else target.from_user.id
    text = await ctx.health.build_health_report(actor_telegram_user_id=actor_id)
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb.to_menu())
    else:
        await target.message.edit_text(text, reply_markup=kb.to_menu())
        await target.answer()


@router.message(Command("health"))
async def cmd_health(message: Message, ctx: AppContext) -> None:
    await ctx.roles.require_access(message.from_user.id)
    await _send_health(message, ctx=ctx)


@router.callback_query(lambda c: c.data == "health:show")
async def health_show(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    await _send_health(callback, ctx=ctx)

