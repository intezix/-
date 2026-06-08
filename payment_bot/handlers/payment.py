from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from payment_bot.app_context import AppContext
from payment_bot.db.repositories import PaymentRepository, SubscriptionRepository, UserRepository
from payment_bot.services.payment_service import PaymentService
from payment_bot.services.sync_service import SubscriptionSyncService
from payment_bot.states.payment import PaymentStates
from payment_bot.ui.copy import (
    ASK_EMAIL_TEXT,
    INVALID_EMAIL_TEXT,
    PAYMENT_CREATE_ERROR_TEXT,
    PAYMENT_CREATED_TEXT,
    PAYMENT_NOT_FOUND_TEXT,
    PAYMENT_PENDING_TEXT,
    PAYMENT_TEMP_UNAVAILABLE_TEXT,
)
from payment_bot.ui.flow import (
    CORE_PAYWALL_KEY,
    EMAIL_PROMPT_MESSAGE_ID_KEY,
    PAYMENT_CTA_MESSAGE_ID_KEY,
    PENDING_MESSAGE_ID_KEY,
    SCREEN_PAYWALL,
    activate_success_flow,
    clear_payment_intermediate_messages,
    clear_payment_flow_after_success,
    get_current_screen,
    get_tracked_message_id,
    set_current_screen,
    set_tracked_message_id,
    strip_reply_markup_safe,
)
from payment_bot.ui.keyboards import payment_action_kb
from payment_bot.ui.onboarding_flow import (
    render_community_success,
    send_paywall_block,
    send_preview_block,
)
from payment_bot.utils.email import is_valid_email
from events_writer import log_event
from pp_common.effective_subscription import get_effective_subscription_state

router = Router()
logger = logging.getLogger(__name__)


def _is_message_not_modified(exc: TelegramBadRequest) -> bool:
    return "message is not modified" in str(exc).lower()


async def _safe_callback_answer(callback: CallbackQuery, *args, **kwargs) -> None:
    try:
        await callback.answer(*args, **kwargs)
    except TelegramBadRequest as exc:
        logger.warning("Callback answer skipped: %s", exc)


async def _has_active_subscription(app_ctx: AppContext, telegram_user_id: int) -> bool:
    assert app_ctx.db.pool is not None
    async with app_ctx.db.pool.acquire() as conn:
        eff = await get_effective_subscription_state(conn, telegram_user_id)
        return eff["status"] == "active"


@router.callback_query(F.data == "onb:continue")
async def onb_continue(callback: CallbackQuery, state: FSMContext, app_ctx: AppContext) -> None:
    await _safe_callback_answer(callback)
    await log_event(
        source_bot="payment_bot",
        telegram_user_id=callback.from_user.id,
        event_type="UI_CALLBACK",
        action="Далее",
        screen=await get_current_screen(state),
        status="ok",
        payload_json={},
        callback_data=callback.data,
        username=callback.from_user.username,
    )
    if await _has_active_subscription(app_ctx, callback.from_user.id):
        await render_community_success(callback.message, state, app_ctx, refresh=True)
        return
    await send_preview_block(callback.message, state, app_ctx)


@router.callback_query(F.data == "onb:open_access")
async def onb_open_access(callback: CallbackQuery, state: FSMContext, app_ctx: AppContext) -> None:
    await _safe_callback_answer(callback)
    await log_event(
        source_bot="payment_bot",
        telegram_user_id=callback.from_user.id,
        event_type="UI_CALLBACK",
        action="Открыть полный доступ",
        screen=await get_current_screen(state),
        status="ok",
        payload_json={},
        callback_data=callback.data,
        username=callback.from_user.username,
    )
    if await _has_active_subscription(app_ctx, callback.from_user.id):
        await render_community_success(callback.message, state, app_ctx, refresh=True)
        return
    await send_paywall_block(callback.message, state, app_ctx)


@router.callback_query(F.data == "pay:open")
async def pay_open(callback: CallbackQuery, state: FSMContext, app_ctx: AppContext) -> None:
    tg_user = callback.from_user
    if app_ctx.debounce.is_limited(tg_user.id, "pay_open"):
        await _safe_callback_answer(callback, "Слишком часто. Попробуйте через пару секунд.", show_alert=True)
        return
    await _safe_callback_answer(callback)
    await log_event(
        source_bot="payment_bot",
        telegram_user_id=tg_user.id,
        event_type="PAY_OPEN",
        action="Оплатить",
        screen=await get_current_screen(state),
        status="ok",
        payload_json={},
        callback_data=callback.data,
        username=tg_user.username,
    )

    if await _has_active_subscription(app_ctx, tg_user.id):
        await render_community_success(callback.message, state, app_ctx, refresh=True)
        return

    paywall_id = await get_tracked_message_id(state, CORE_PAYWALL_KEY)
    if paywall_id and callback.message:
        await strip_reply_markup_safe(callback.bot, callback.message.chat.id, paywall_id)

    assert app_ctx.db.pool is not None
    async with app_ctx.db.pool.acquire() as conn:
        user_repo = UserRepository(conn)
        await user_repo.upsert_user(tg_user.id, tg_user.username)
        user = await user_repo.get_user_by_telegram_id(tg_user.id)
        if not user or not user["email"]:
            await state.set_state(PaymentStates.waiting_for_email)
            email_prompt_id = await get_tracked_message_id(state, EMAIL_PROMPT_MESSAGE_ID_KEY)
            if email_prompt_id:
                try:
                    await callback.bot.edit_message_text(
                        chat_id=callback.message.chat.id,
                        message_id=email_prompt_id,
                        text=ASK_EMAIL_TEXT,
                    )
                    return
                except TelegramBadRequest:
                    pass
            sent = await callback.message.answer(ASK_EMAIL_TEXT)
            await set_tracked_message_id(state, EMAIL_PROMPT_MESSAGE_ID_KEY, sent.message_id)
            return

        service = PaymentService(conn, app_ctx.settings, app_ctx.yookassa)
        try:
            payment = await service.create_or_get_pending_payment(tg_user.id, tg_user.username)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to create payment")
            await log_event(
                source_bot="payment_bot",
                telegram_user_id=tg_user.id,
                event_type="PAY_CREATE_FAILED",
                action="Создание платежа",
                screen=await get_current_screen(state),
                status="error",
                payload_json={},
                error_message=str(exc),
                traceback=__import__("traceback").format_exc(),
                username=tg_user.username,
            )
            await callback.message.answer(PAYMENT_CREATE_ERROR_TEXT)
            return
        url = payment.get("confirmation", {}).get("confirmation_url")
        if not url:
            await callback.message.answer(PAYMENT_TEMP_UNAVAILABLE_TEXT)
            return
        await log_event(
            source_bot="payment_bot",
            telegram_user_id=tg_user.id,
            event_type="PAY_CREATED",
            action="Платёж создан",
            screen=await get_current_screen(state),
            status="ok",
            payload_json={"payment_id": payment.get("id")},
            username=tg_user.username,
        )
        payment_msg_id = await get_tracked_message_id(state, PAYMENT_CTA_MESSAGE_ID_KEY)
        if payment_msg_id:
            try:
                await callback.bot.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=payment_msg_id,
                    text=PAYMENT_CREATED_TEXT,
                    reply_markup=payment_action_kb(url),
                )
                return
            except TelegramBadRequest as exc:
                if _is_message_not_modified(exc):
                    return
        sent = await callback.message.answer(PAYMENT_CREATED_TEXT, reply_markup=payment_action_kb(url))
        await set_tracked_message_id(state, PAYMENT_CTA_MESSAGE_ID_KEY, sent.message_id)


@router.message(PaymentStates.waiting_for_email)
async def save_email_and_pay(message: Message, state: FSMContext, app_ctx: AppContext) -> None:
    email = (message.text or "").strip().lower()
    if not is_valid_email(email):
        await message.answer(INVALID_EMAIL_TEXT)
        return

    assert app_ctx.db.pool is not None
    async with app_ctx.db.pool.acquire() as conn:
        user_repo = UserRepository(conn)
        await user_repo.upsert_user(message.from_user.id, message.from_user.username)
        await user_repo.set_email(message.from_user.id, email)
        service = PaymentService(conn, app_ctx.settings, app_ctx.yookassa)
        try:
            payment = await service.create_or_get_pending_payment(message.from_user.id, message.from_user.username)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to create payment after email")
            await log_event(
                source_bot="payment_bot",
                telegram_user_id=message.from_user.id,
                event_type="PAY_CREATE_FAILED",
                action="Создание платежа после email",
                screen=await get_current_screen(state),
                status="error",
                payload_json={"email": email},
                error_message="Failed to create payment after email",
                traceback=__import__("traceback").format_exc(),
                username=message.from_user.username,
            )
            await message.answer(PAYMENT_CREATE_ERROR_TEXT)
            return

    await state.set_state(None)
    await clear_payment_intermediate_messages(message.bot, message.chat.id, state)
    url = payment.get("confirmation", {}).get("confirmation_url")
    if not url:
        await message.answer(PAYMENT_TEMP_UNAVAILABLE_TEXT)
        return
    sent = await message.answer(PAYMENT_CREATED_TEXT, reply_markup=payment_action_kb(url))
    await set_tracked_message_id(state, PAYMENT_CTA_MESSAGE_ID_KEY, sent.message_id)
    await log_event(
        source_bot="payment_bot",
        telegram_user_id=message.from_user.id,
        event_type="PAY_LINK_SENT",
        action="Ссылка на оплату отправлена",
        screen=await get_current_screen(state),
        status="ok",
        payload_json={"payment_id": payment.get("id")},
        username=message.from_user.username,
    )


@router.callback_query(F.data == "pay:check_last")
async def pay_check_last(callback: CallbackQuery, state: FSMContext, app_ctx: AppContext) -> None:
    tg_user = callback.from_user
    if app_ctx.debounce.is_limited(tg_user.id, "pay_check"):
        await _safe_callback_answer(callback, "Слишком часто. Подождите 2 секунды.", show_alert=True)
        return
    await _safe_callback_answer(callback)
    await log_event(
        source_bot="payment_bot",
        telegram_user_id=tg_user.id,
        event_type="PAY_CHECK",
        action="Оплатил",
        screen=await get_current_screen(state),
        status="ok",
        payload_json={},
        callback_data=callback.data,
        username=tg_user.username,
    )

    status = "not_found"
    assert app_ctx.db.pool is not None
    async with app_ctx.db.pool.acquire() as conn:
        user_repo = UserRepository(conn)
        payment_repo = PaymentRepository(conn)
        user = await user_repo.get_user_by_telegram_id(tg_user.id)
        if not user:
            await callback.message.answer(PAYMENT_NOT_FOUND_TEXT)
            return
        pending = await payment_repo.find_recent_pending_payment(user["id"], app_ctx.settings.pending_payment_ttl_minutes)
        eff = await get_effective_subscription_state(conn, tg_user.id)
        if eff["status"] == "active":
            status = "succeeded"
            pending = None
        if not pending:
            if status != "succeeded":
                await callback.message.answer(PAYMENT_NOT_FOUND_TEXT)
                return
        else:
            service = PaymentService(conn, app_ctx.settings, app_ctx.yookassa)
            try:
                status = await service.process_payment_status(pending["payment_id"], source="manual_check")
            except ValueError as exc:
                if str(exc) == "PAYMENT_NOT_FOUND":
                    await callback.message.answer(PAYMENT_NOT_FOUND_TEXT)
                    return
                raise
            except Exception:  # noqa: BLE001
                logger.exception("Payment check failed")
                await log_event(
                    source_bot="payment_bot",
                    telegram_user_id=tg_user.id,
                    event_type="PAY_CHECK_FAILED",
                    action="Проверка оплаты",
                    screen=await get_current_screen(state),
                    status="error",
                    payload_json={"payment_id": pending["payment_id"]},
                    error_message="Payment check failed",
                    traceback=__import__("traceback").format_exc(),
                    username=tg_user.username,
                )
                await callback.message.answer(PAYMENT_TEMP_UNAVAILABLE_TEXT)
                return

    if status == "succeeded":
        await log_event(
            source_bot="payment_bot",
            telegram_user_id=tg_user.id,
            event_type="PAY_SUCCEEDED",
            action="Оплата успешна",
            screen=await get_current_screen(state),
            status="ok",
            payload_json={},
            username=tg_user.username,
        )
        if callback.message:
            await clear_payment_flow_after_success(callback.bot, callback.message.chat.id, state)
            await activate_success_flow(callback.bot, callback.message.chat.id, state)
        await render_community_success(callback.message, state, app_ctx, refresh=True)
        async with app_ctx.db.pool.acquire() as conn:
            sub_repo = SubscriptionRepository(conn)
            user = await UserRepository(conn).get_user_by_telegram_id(tg_user.id)
            if user:
                sub = await sub_repo.get_by_user_id(user["id"])
                if sub:
                    SubscriptionSyncService.sync_subscription_to_main_bot(
                        user_telegram_id=tg_user.id,
                        status=sub["status"],
                        paid_until=sub["paid_until"],
                        canceled_at=sub.get("canceled_at"),
                    )
    elif status == "pending":
        await log_event(
            source_bot="payment_bot",
            telegram_user_id=tg_user.id,
            event_type="PAY_PENDING",
            action="Платёж в обработке",
            screen=await get_current_screen(state),
            status="warn",
            payload_json={},
            username=tg_user.username,
        )
        pending_msg_id = await get_tracked_message_id(state, PENDING_MESSAGE_ID_KEY)
        if pending_msg_id:
            try:
                await callback.bot.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=pending_msg_id,
                    text=PAYMENT_PENDING_TEXT,
                )
                return
            except TelegramBadRequest as exc:
                if _is_message_not_modified(exc):
                    return
        sent = await callback.message.answer(PAYMENT_PENDING_TEXT)
        await set_tracked_message_id(state, PENDING_MESSAGE_ID_KEY, sent.message_id)
        await set_current_screen(state, SCREEN_PAYWALL)
    else:
        await log_event(
            source_bot="payment_bot",
            telegram_user_id=tg_user.id,
            event_type="PAY_FAILED",
            action="Платёж не прошёл",
            screen=await get_current_screen(state),
            status="error",
            payload_json={},
            username=tg_user.username,
        )
        await callback.message.answer(PAYMENT_NOT_FOUND_TEXT)
