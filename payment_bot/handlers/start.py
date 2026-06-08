from __future__ import annotations

from pp_common.effective_subscription import get_effective_subscription_state

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from payment_bot.app_context import AppContext
from payment_bot.ui.copy import WELCOME_STEP1
from payment_bot.ui.flow import (
    ALL_KEYS,
    CORE_WELCOME1_KEY,
    SCREEN_WELCOME_1,
    cleanup_tracked_messages,
    set_current_screen,
    set_tracked_message_id,
)
from payment_bot.ui.keyboards import onboarding_next_kb
from payment_bot.ui.onboarding_flow import render_community_success

router = Router()


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext, app_ctx: AppContext) -> None:
    assert app_ctx.db.pool is not None
    async with app_ctx.db.pool.acquire() as conn:
        eff = await get_effective_subscription_state(conn, message.from_user.id)
        is_active = eff["status"] == "active"

    if is_active:
        await render_community_success(message, state, app_ctx, refresh=True)
        return

    await cleanup_tracked_messages(message.bot, message.chat.id, state, ALL_KEYS)
    sent = await message.answer(WELCOME_STEP1, reply_markup=onboarding_next_kb(), parse_mode="HTML")
    await set_tracked_message_id(state, CORE_WELCOME1_KEY, sent.message_id)
    await set_current_screen(state, SCREEN_WELCOME_1)
