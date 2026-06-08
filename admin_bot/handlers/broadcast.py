from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from admin_bot.app_context import AppContext
from admin_bot.keyboards.inline import InlineKeyboards
from admin_bot.states.admin import BroadcastStates


router = Router()
kb = InlineKeyboards()
logger = logging.getLogger(__name__)


# ── Шаг 1: получаем текст от администратора ──────────────────────────────────

@router.message(StateFilter(BroadcastStates.waiting_for_text))
async def broadcast_got_text(message: Message, state: FSMContext, ctx: AppContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не может быть пустым. Введите текст сообщения:", reply_markup=kb.cancel_fsm_kb("nav:menu"))
        return

    # Сохраняем текст в FSM, переходим к шагу подтверждения
    await state.update_data(broadcast_text=text)
    await state.set_state(BroadcastStates.waiting_confirm)

    # Показываем предпросмотр
    preview = "\n".join(
        [
            "📢 <b>Предпросмотр рассылки</b>",
            "",
            "Сообщение будет выглядеть так:",
            "─────────────────────",
            text,
            "─────────────────────",
            "",
            "Подтвердите отправку всем пользователям.",
        ]
    )
    await message.answer(preview, reply_markup=kb.broadcast_confirm())


# ── Шаг 2a: подтверждение — отправить ────────────────────────────────────────

@router.callback_query(lambda c: c.data == "broadcast:confirm")
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    if not text:
        await callback.answer("Текст рассылки не найден. Начните заново.", show_alert=True)
        await state.clear()
        return
    await state.clear()

    # Показываем прогресс
    await callback.message.edit_text("📢 <b>Рассылка запущена…</b>\n\nЭто может занять несколько минут.")
    await callback.answer()

    try:
        result = await ctx.broadcast.send_to_all(
            actor_telegram_user_id=callback.from_user.id,
            text=text,
        )
    except Exception as exc:
        logger.exception("broadcast failed: %s", exc)
        await callback.message.edit_text(
            f"❌ Ошибка при рассылке:\n<code>{exc}</code>",
            reply_markup=kb.to_menu(),
        )
        return

    lines = [
        "📢 <b>Рассылка завершена</b>",
        "",
        f"📊 Всего пользователей: <b>{result.total}</b>",
        f"✅ Отправлено: <b>{result.sent}</b>",
        f"🚫 Заблокировали бота: <b>{result.blocked}</b>",
        f"❌ Ошибок: <b>{result.errors}</b>",
    ]
    if result.stopped_early:
        lines.append("\n⚠️ Рассылка прервана досрочно из-за большого числа ошибок.")

    await callback.message.edit_text("\n".join(lines), reply_markup=kb.to_menu())
    logger.info(
        "broadcast by %s: total=%s sent=%s blocked=%s errors=%s",
        callback.from_user.id, result.total, result.sent, result.blocked, result.errors,
    )


# ── Шаг 2b: изменить текст (вернуться к вводу) ───────────────────────────────

@router.callback_query(lambda c: c.data == "broadcast:edit")
async def broadcast_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BroadcastStates.waiting_for_text)
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\nВведите новый текст сообщения:",
        reply_markup=kb.cancel_fsm_kb("nav:menu"),
    )
    await callback.answer()
