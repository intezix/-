from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from config import Texts
from services.user_activity_service import UserActivityService

logger = logging.getLogger(__name__)
_activity_service = UserActivityService()

INACTIVITY_START_CALLBACK = "inactivity:start"


def is_start_over_text(text: str | None) -> bool:
    if not text:
        return False
    normalized = text.strip().casefold()
    return normalized in {Texts.START_OVER.casefold(), "начать".casefold()}


def is_inactivity_start_callback(data: str | None) -> bool:
    return data == INACTIVITY_START_CALLBACK


async def dismiss_reply_keyboard(bot: Bot, chat_id: int) -> None:
    """Снимает залипшую reply-клавиатуру (в т.ч. после старых напоминаний)."""
    try:
        tmp = await bot.send_message(chat_id, "\u2060", reply_markup=ReplyKeyboardRemove())
        try:
            await bot.delete_message(chat_id=chat_id, message_id=tmp.message_id)
        except Exception:
            pass
    except Exception:
        logger.debug("dismiss_reply_keyboard failed chat_id=%s", chat_id, exc_info=True)


async def resolve_inactivity_prompt_message_id(user_id: int) -> Optional[int]:
    from services.ui_registry import get_user_ui_messages

    rows = get_user_ui_messages(user_id)
    inactivity_rows = [r for r in rows if r.kind == "inactivity_start"]
    if inactivity_rows:
        return inactivity_rows[-1].message_id
    return _activity_service.get_reminder_message_id(user_id)


async def delete_telegram_message(bot: Bot, chat_id: int, message_id: int | None) -> None:
    if message_id is None:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        try:
            await bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=None,
            )
        except Exception:
            pass


async def process_start_over(
    *,
    user_id: int,
    chat_id: int,
    bot: Bot,
    state: FSMContext,
    anchor_message: Message,
    prompt_message_id: Optional[int] = None,
    delete_user_message: bool = False,
) -> None:
    """
    Полный сброс UI после неактивности / нажатия «НАЧАТЬ».
    Работает даже если ui_registry или reminder в БД рассинхронизированы.
    """
    if delete_user_message and anchor_message.text and is_start_over_text(anchor_message.text):
        try:
            await anchor_message.delete()
        except Exception:
            pass

    await dismiss_reply_keyboard(bot, chat_id)

    if prompt_message_id is None:
        prompt_message_id = await resolve_inactivity_prompt_message_id(user_id)

    # Ленивый импорт — избегаем циклов handlers ↔ services.
    from handlers.inline_handlers import on_inactivity_start

    await on_inactivity_start(
        user_id=user_id,
        chat_id=chat_id,
        current_start_message_id=prompt_message_id,
        message=anchor_message,
        state=state,
    )
