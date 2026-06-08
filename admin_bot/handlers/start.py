from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from admin_bot.app_context import AppContext
from admin_bot.keyboards.inline import InlineKeyboards


router = Router()
kb = InlineKeyboards()


@router.message(Command("start"))
@router.message(Command("admin"))
async def cmd_admin(message: Message, ctx: AppContext, state: FSMContext) -> None:
    # Сброс любого активного FSM-состояния
    await state.clear()

    # Проверка доступа — если нет, молча отказываем
    try:
        await ctx.roles.require_access(message.from_user.id)
    except PermissionError:
        await message.answer("⛔ Нет доступа.")
        return

    text = "\n".join(
        [
            "⚙️ <b>Админ-бот PP BOT</b>",
            "",
            "Выберите раздел.",
        ]
    )
    await message.answer(text, reply_markup=kb.menu())
