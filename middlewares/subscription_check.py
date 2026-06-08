import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update
from aiogram.fsm.context import FSMContext

from config import Texts
from services.effective_subscription_service import get_effective_state
from services.inactivity_flow import is_inactivity_start_callback, is_start_over_text

logger = logging.getLogger(__name__)

PAYMENT_BOT_URL = "https://t.me/paybykatti_ppbot"
SUBSCRIPTION_EXPIRED_TEXT = (
    f"<b>К сожалению, ваша подписка закончилась 😔</b>\n\n"
    f"Доступ к рецептам временно ограничен.\n\n"
    f"<i>Нажмите кнопку ниже, чтобы продлить подписку →</i>"
)


class SubscriptionCheckMiddleware(BaseMiddleware):
    """Middleware для проверки статуса подписки перед обработкой команд."""

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        # Определяем user_id из update
        user_id: int | None = None
        is_callback = False

        if event.message and event.message.from_user:
            user_id = event.message.from_user.id
        elif event.callback_query and event.callback_query.from_user:
            user_id = event.callback_query.from_user.id
            is_callback = True

        # Пропускаем /start и сброс после неактивности
        if event.message and event.message.text == "/start":
            return await handler(event, data)
        if event.message and is_start_over_text(event.message.text):
            return await handler(event, data)
        if event.callback_query and is_inactivity_start_callback(event.callback_query.data):
            return await handler(event, data)

        # Если пользователь найден, проверяем подписку
        if user_id:
            try:
                eff = await get_effective_state(user_id)
                has_active = eff["status"] == "active"
            except Exception as e:
                # Fail-safe: do not accidentally grant access if DB is unavailable.
                logger.exception("Effective subscription check failed for user %s: %s", user_id, e)
                has_active = False

            # Если подписка неактивна, показываем сообщение
            if not has_active:
                # Для callback query отвечаем в чат
                if is_callback and event.callback_query and event.callback_query.message:
                    try:
                        # Очищаем состояние
                        state: FSMContext = data.get("state")
                        if state:
                            await state.clear()

                        # Отправляем сообщение с ссылкой на платёжного бота
                        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

                        keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [InlineKeyboardButton(text="💳 Оплатить подписку", url=PAYMENT_BOT_URL)],
                            ]
                        )

                        await event.callback_query.message.answer(
                            SUBSCRIPTION_EXPIRED_TEXT,
                            reply_markup=keyboard,
                            protect_content=False,
                        )
                    except Exception as e:
                        logger.exception(f"Failed to send subscription expired message: {e}")
                    return  # Не обрабатываем дальше

                # Для обычных сообщений
                elif event.message:
                    try:
                        # Очищаем состояние
                        state: FSMContext = data.get("state")
                        if state:
                            await state.clear()

                        # Отправляем сообщение с ссылкой на платёжного бота
                        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

                        keyboard = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [InlineKeyboardButton(text="💳 Оплатить подписку", url=PAYMENT_BOT_URL)],
                            ]
                        )

                        await event.message.answer(
                            SUBSCRIPTION_EXPIRED_TEXT,
                            reply_markup=keyboard,
                            protect_content=False,
                        )
                    except Exception as e:
                        logger.exception(f"Failed to send subscription expired message: {e}")
                    return  # Не обрабатываем дальше

        # Продолжаем обработку если подписка активна
        return await handler(event, data)
