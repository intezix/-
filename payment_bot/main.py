from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher

from payment_bot.app_context import AppContext
from payment_bot.config import load_settings
from payment_bot.db.database import Database
from payment_bot.handlers.payment import router as payment_router
from payment_bot.handlers.start import router as start_router
from payment_bot.services.admin_notify_service import AdminNotifyService
from payment_bot.services.outbox_service import OutboxService
from payment_bot.services.rate_limit_service import CallbackDebounceService
from payment_bot.services.yookassa_service import YooKassaService
from payment_bot.utils.logging import setup_logging
from payment_bot.webhook_app import build_webhook_app

logger = logging.getLogger(__name__)


async def monitoring_loop(app_ctx: AppContext, stop_event: asyncio.Event) -> None:
    """Отчёт мониторинга каждые 12 часов в admin-чат."""
    from payment_bot.db.admin_queries import AdminRepository
    from datetime import UTC, datetime
    INTERVAL = 12 * 3600
    while not stop_event.is_set():
        await asyncio.sleep(INTERVAL)
        if stop_event.is_set():
            break
        try:
            assert app_ctx.db.pool is not None
            async with app_ctx.db.pool.acquire() as conn:
                admin_repo = AdminRepository(conn)
                info = await admin_repo.get_monitoring_info()
                stats = await admin_repo.get_stats(1)  # За сутки

            now = datetime.now(UTC).strftime("%d.%m.%Y %H:%M UTC")
            report = (
                f"🔭 <b>Автоотчёт мониторинга</b> ({now})\n\n"
                f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
                f"💳 Активных подписок: <b>{stats['subs_active']}</b>\n"
                f"💰 Платежей за 24ч: <b>{stats['payments_count']}</b> ({stats['payments_revenue']:.0f} ₽)\n"
                f"❌ Ошибок за 24ч: <b>{stats['errors_count']}</b>\n\n"
                f"📬 Outbox: ⏳{info['outbox_pending']} pending | 🔁{info['outbox_retry']} retry | ❌{info['outbox_failed']} failed"
            )
            kwargs = {}
            if app_ctx.settings.admin_email_thread_id:
                kwargs["message_thread_id"] = app_ctx.settings.admin_email_thread_id
            await app_ctx.bot.send_message(
                chat_id=app_ctx.settings.admin_email_chat_id,
                text=report,
                parse_mode="HTML",
                **kwargs,
            )
        except Exception:
            logger.exception("Monitoring loop iteration failed")


async def outbox_loop(app_ctx: AppContext, stop_event: asyncio.Event) -> None:
    assert app_ctx.db.pool is not None
    while not stop_event.is_set():
        try:
            async with app_ctx.db.pool.acquire() as conn:
                notify = AdminNotifyService(
                    bot=app_ctx.bot,
                    chat_id=app_ctx.settings.admin_email_chat_id,
                    thread_id=app_ctx.settings.admin_email_thread_id,
                )
                outbox = OutboxService(conn, notify)
                await outbox.process_batch(limit=50)
        except Exception:  # noqa: BLE001
            # Background loop must never die silently; log and keep retrying.
            logger.exception("Outbox loop iteration failed")
        await asyncio.sleep(2)


async def run() -> None:
    settings = load_settings()
    setup_logging(settings.log_level)

    db = Database(settings.postgres_dsn)
    await db.connect()

    bot = Bot(settings.bot_token)
    yookassa = YooKassaService(settings.yookassa_shop_id, settings.yookassa_secret_key)
    app_ctx = AppContext(
        settings=settings,
        db=db,
        bot=bot,
        yookassa=yookassa,
        debounce=CallbackDebounceService(settings.rate_limit_seconds),
    )

    dp = Dispatcher()
    dp.include_router(start_router)
    dp.include_router(payment_router)
    dp["app_ctx"] = app_ctx

    stop_event = asyncio.Event()
    outbox_task = asyncio.create_task(outbox_loop(app_ctx, stop_event))
    monitoring_task = asyncio.create_task(monitoring_loop(app_ctx, stop_event))

    if settings.bot_mode == "webhook":
        await bot.set_webhook(
            url=settings.telegram_webhook_url,
            secret_token=settings.telegram_webhook_secret,
            drop_pending_updates=False,
        )
        app = build_webhook_app(dp, bot, app_ctx)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=8080)
        await site.start()
        logger.info("Payment bot webhook app started on :8080")
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Payment bot started in polling mode")

    try:
        if settings.bot_mode == "polling":
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        else:
            while True:
                await asyncio.sleep(3600)
    finally:
        stop_event.set()
        outbox_task.cancel()
        monitoring_task.cancel()
        if settings.bot_mode == "webhook":
            await bot.delete_webhook(drop_pending_updates=False)
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(run())

