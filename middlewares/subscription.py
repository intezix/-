from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import Update, Message, CallbackQuery
from config import UX_MODE, UXMode, Texts, PROTECT_CONTENT
from services.subscription_service import SubscriptionService
from keyboards import InlineKeyboards
from keyboards.inline import CallbackData
from states import BillingState


class SubscriptionMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._service = SubscriptionService()

    async def __call__(self, handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]], event: Update, data: Dict[str, Any]) -> Any:
        message: Optional[Message] = event.message or event.edited_message
        callback: Optional[CallbackQuery] = event.callback_query
        state = data.get("state")
        user_id: Optional[int] = None
        if message and message.from_user:
            user_id = message.from_user.id
        elif callback and callback.from_user:
            user_id = callback.from_user.id
        if user_id is None:
            return await handler(event, data)
        if self._service.has_active_subscription(user_id):
            return await handler(event, data)
        # Разрешаем ввод email на шаге BillingState.waiting_email
        if state is not None:
            try:
                current_state = await state.get_state()
            except Exception:
                current_state = None
            if current_state == BillingState.waiting_email.state:
                return await handler(event, data)
        if callback:
            data_str = callback.data or ""
            # Разрешаем callback'и, связанные с онбордингом и оплатой
            if data_str in (
                CallbackData.WELCOME_CONTINUE,
                CallbackData.WELCOME_PAY,
            ) or data_str.startswith(f"{CallbackData.SUBSCRIPTION_CHECK}:"):
                return await handler(event, data)
        if message:
            text = (message.text or "").strip()
            if text.startswith("/start") or text in (Texts.CONTINUE, Texts.PAY, Texts.GO_TO_CATEGORIES):
                return await handler(event, data)
        if callback and callback.message:
            await callback.answer()
            markup = InlineKeyboards.welcome_step2()
            await callback.message.answer(Texts.WELCOME_STEP2, reply_markup=markup, protect_content=PROTECT_CONTENT)
            return
        if message:
            markup = InlineKeyboards.welcome_step2()
            await message.answer(Texts.WELCOME_STEP2, reply_markup=markup, protect_content=PROTECT_CONTENT)
            return
        return await handler(event, data)

