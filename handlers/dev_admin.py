from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import PROTECT_CONTENT
from handlers.dev_access import is_dev_admin_message
from keyboards import ReplyKeyboards
from services.user_activity_service import UserActivityService

router = Router()

DEFAULT_UPDATE_TEXT = (
    "<b>Обновление</b>\n\n"
    "Если бот перестал отвечать или кнопки работают некорректно — введите команду:\n"
    "<code>/start</code>\n\n"
    "Спасибо 🤍"
)


@router.message(Command("update"))
async def dev_broadcast_update(message: Message) -> None:
    if not is_dev_admin_message(message):
        return

    # Allow custom text after command: /update some text...
    text = (message.text or "").strip()
    custom = text.split(" ", 1)[1].strip() if " " in text else ""
    payload = custom or DEFAULT_UPDATE_TEXT

    service = UserActivityService()
    user_ids = service.get_all_user_ids()
    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(chat_id=uid, text=payload, parse_mode="HTML", protect_content=PROTECT_CONTENT)
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"Готово. Отправлено: {sent}, ошибок: {failed}",
        protect_content=PROTECT_CONTENT,
    )


@router.message(Command("test_reminder"))
async def cmd_test_reminder(message: Message) -> None:
    """Тест напоминания о неактивности — только DEV_ADMIN_IDS."""
    if not is_dev_admin_message(message):
        return

    user_id = message.from_user.id
    try:
        keyboard = ReplyKeyboards.start_over()
        text = (
            "Ты давно не заходил в бот 🤍\n\n"
            "Нажми кнопку ниже, чтобы снова выбрать приём пищи и рецепты."
        )
        msg = await message.answer(text, reply_markup=keyboard, protect_content=PROTECT_CONTENT)
        service = UserActivityService()
        service.set_reminder(user_id, msg.message_id)
        from services.ui_registry import register_ui_message

        register_ui_message(
            user_id=user_id,
            chat_id=user_id,
            message_id=msg.message_id,
            kind="inactivity_start",
            is_persistent=False,
        )
        await message.answer("✅ Тестовое напоминание отправлено!", protect_content=PROTECT_CONTENT)
    except Exception as e:
        import traceback

        await message.answer(
            f"❌ Ошибка: {e}\n\n{traceback.format_exc()}",
            protect_content=PROTECT_CONTENT,
        )

