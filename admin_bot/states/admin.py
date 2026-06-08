from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddAdminStates(StatesGroup):
    """FSM для добавления нового администратора через кнопку «➕ Добавить»."""
    waiting_for_id = State()   # ожидаем Telegram ID


class GrantDaysStates(StatesGroup):
    """FSM для выдачи произвольного числа дней через кнопку «✏️ Другое»."""
    waiting_for_days = State()  # ожидаем число дней


class BroadcastStates(StatesGroup):
    """FSM для рассылки сообщений всем пользователям."""
    waiting_for_text = State()    # ожидаем текст сообщения
    waiting_confirm = State()     # текст введён, ждём нажатия «Отправить»
