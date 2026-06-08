from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from handlers.common import show_welcome_screen
from services.ui_registry import clear_user_ui_session
from events_writer import log_event
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # Ensure /start is idempotent: cleanup old UI messages first.
    if message.from_user:
        await clear_user_ui_session(user_id=message.from_user.id, preserve_persistent=False, bot=message.bot)
        await log_event(
            source_bot="main_bot",
            telegram_user_id=message.from_user.id,
            event_type="START",
            action="/start",
            screen="welcome_1",
            status="ok",
            payload_json={},
            username=message.from_user.username,
            message_text=message.text,
        )
    await show_welcome_screen(message, state)
