from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import logging
from config import Texts, PROTECT_CONTENT
from states import BillingState, UserState
from services.subscription_service import SubscriptionService
from keyboards import InlineKeyboards
from keyboards.inline import CallbackData


router = Router()
service = SubscriptionService()
logger = logging.getLogger(__name__)


async def start_subscription_from_message(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    current_state = await state.get_state()
    has_sub = service.has_active_subscription(user_id)
    logger.info(
        "billing.start_from_message: text=%r state=%r has_active_subscription=%s",
        (message.text or "").strip(),
        current_state,
        has_sub,
    )
    if has_sub:
        from handlers.common import show_welcome_step3

        logger.info("billing.start_from_message branch=already_subscribed user_id=%s", user_id)
        await show_welcome_step3(message, state)
        return
    email = service.get_email(user_id)
    if not email:
        logger.info("billing.start_from_message branch=waiting_email user_id=%s", user_id)
        await state.set_state(BillingState.waiting_email)
        await message.answer("Напиши email, на который прислать чек.", protect_content=PROTECT_CONTENT)
        return
    logger.info("billing.start_from_message branch=create_payment user_id=%s email=%s", user_id, email)
    payment_id, confirmation_url = service.create_payment(user_id, email)
    markup = InlineKeyboards.subscription_payment(confirmation_url, payment_id)
    text = "Оформи подписку PP BOT на 30 дней за 499 ₽.\n\nНажми «Перейти к оплате», а после успешной оплаты — кнопку «Я оплатил — проверить»."
    await message.answer(text, reply_markup=markup, protect_content=PROTECT_CONTENT)
    await state.set_state(UserState.welcome_step2)


async def start_subscription_from_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if not callback.message:
        return
    user_id = callback.from_user.id
    data_str = callback.data or ""
    current_state = await state.get_state()
    has_sub = service.has_active_subscription(user_id)
    logger.info(
        "billing.start_from_callback: callback_data=%r state=%r has_active_subscription=%s",
        data_str,
        current_state,
        has_sub,
    )
    logger.info("billing.start_from_callback branch=delegate_to_message_handler user_id=%s", user_id)
    await start_subscription_from_message(callback.message, state)


@router.message(BillingState.waiting_email)
async def handle_billing_email(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    email = (message.text or "").strip()
    if not service.is_email_valid(email):
        await message.answer("Это не похоже на email. Пришли корректный email, например example@mail.ru.", protect_content=PROTECT_CONTENT)
        return
    service.set_email(user_id, email)
    await message.answer("Email сохранен. Создаю ссылку на оплату.", protect_content=PROTECT_CONTENT)
    payment_id, confirmation_url = service.create_payment(user_id, email)
    markup = InlineKeyboards.subscription_payment(confirmation_url, payment_id)
    text = "Оформи подписку PP BOT на 30 дней за 499 ₽.\n\nНажми «Перейти к оплате», а после успешной оплаты — кнопку «Я оплатил — проверить»."
    await message.answer(text, reply_markup=markup, protect_content=PROTECT_CONTENT)
    await state.set_state(UserState.welcome_step2)


@router.callback_query(F.data.startswith(f"{CallbackData.SUBSCRIPTION_CHECK}:"))
async def handle_subscription_check(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = callback.data or ""
    parts = data.split(":", 1)
    if len(parts) < 2:
        await callback.message.answer("Не удалось найти платеж. Попробуй еще раз оформить подписку.", protect_content=PROTECT_CONTENT)
        return
    payment_id = parts[1]
    try:
        status = service.check_payment_and_update(payment_id)
    except Exception:
        await callback.message.answer("Не удалось проверить платеж. Попробуй через минуту.", protect_content=PROTECT_CONTENT)
        return
    if status == "succeeded":
        from handlers.common import show_welcome_step3

        await callback.message.answer("Оплата прошла успешно. Подписка активирована на 30 дней.", protect_content=PROTECT_CONTENT)
        await show_welcome_step3(callback.message, state)
    elif status in ("pending", "waiting_for_capture"):
        await callback.message.answer("Платеж обрабатывается. Попробуй нажать «Я оплатил — проверить» чуть позже.", protect_content=PROTECT_CONTENT)
    elif status == "canceled":
        await callback.message.answer("Платеж был отменен. Попробуй оформить подписку еще раз.", protect_content=PROTECT_CONTENT)
    else:
        await callback.message.answer("Платеж не прошел. Попробуй еще раз оформить подписку.", protect_content=PROTECT_CONTENT)

