from __future__ import annotations

import asyncio
import logging
import warnings

warnings.filterwarnings("ignore", module="pydantic._internal._fields")

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command, ExceptionTypeFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent, Message
from aiogram.exceptions import TelegramNetworkError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from admin_bot.app_context import build_app_context
from admin_bot.config import load_settings
from admin_bot.handlers import (
    broadcast,
    errors,
    health,
    logs,
    navigation,
    payments,
    roles,
    start,
    subscriptions,
    system,
    test_modes,
    users,
    stats,
)
from admin_bot.monitors.health_report import send_health_report_job
from admin_bot.monitors.error_watcher import error_watcher_job


logger = logging.getLogger(__name__)


def create_bot(token: str) -> Bot:
    session = AiohttpSession(timeout=180)
    return Bot(token=token, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(navigation.router)
    dp.include_router(users.router)
    dp.include_router(subscriptions.router)
    dp.include_router(payments.router)
    dp.include_router(logs.router)
    dp.include_router(errors.router)
    dp.include_router(health.router)
    dp.include_router(stats.router)
    dp.include_router(roles.router)
    dp.include_router(test_modes.router)
    dp.include_router(system.router)
    dp.include_router(broadcast.router)
    return dp


async def main() -> None:
    settings = load_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger.info("🚀 Starting admin_bot (mode=%s)...", settings.bot_mode)

    bot = create_bot(settings.bot_token)
    dp = create_dispatcher()
    ctx = await build_app_context(settings)
    dp["ctx"] = ctx

    # /cancel — сброс любого FSM-состояния + возврат в меню
    @dp.message(Command("cancel"))
    async def cmd_cancel(message: Message, state: FSMContext) -> None:
        from admin_bot.keyboards.inline import InlineKeyboards
        await state.clear()
        await message.answer("✖️ Действие отменено.\n\nВыберите раздел:", reply_markup=InlineKeyboards().menu())

    # Seed owner row (for access gate + notify flags)
    await ctx.roles.ensure_owner_seeded(username=None)

    # Scheduler: 12h health report in DM
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        send_health_report_job,
        CronTrigger.from_crontab(settings.health_report_cron, timezone=settings.timezone),
        args=[bot, ctx],
        id="health_report",
        replace_existing=True,
    )
    scheduler.add_job(
        error_watcher_job,
        IntervalTrigger(seconds=60),
        args=[bot, ctx],
        id="error_watcher",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()

    @dp.error(ExceptionTypeFilter(TelegramNetworkError))
    async def on_network_error(event: ErrorEvent, bot: Bot) -> None:
        logger.warning("TelegramNetworkError: %s", event.exception)

    @dp.error()
    async def on_any_error(event: ErrorEvent) -> bool:
        exc = event.exception
        upd = event.update

        # PermissionError — user lacks role
        if isinstance(exc, PermissionError):
            msg = str(exc) or "⛔ Нет доступа"
            if upd.callback_query:
                try:
                    await upd.callback_query.answer(f"⛔ {msg}", show_alert=True)
                except Exception:
                    pass
            elif upd.message:
                try:
                    await upd.message.answer(f"⛔ {msg}")
                except Exception:
                    pass
            return True

        # ValueError — bad input / not found
        if isinstance(exc, ValueError):
            msg = str(exc) or "Некорректный запрос"
            if upd.callback_query:
                try:
                    await upd.callback_query.answer(f"⚠️ {msg}", show_alert=True)
                except Exception:
                    pass
            elif upd.message:
                try:
                    await upd.message.answer(f"⚠️ {msg}")
                except Exception:
                    pass
            return True

        logger.exception("Unhandled error in update %s: %s", upd.update_id, exc)
        return False

    # Startup webhook cleanup for polling
    for attempt in range(1, 4):
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            break
        except TelegramNetworkError as e:
            if attempt < 3:
                logger.warning("Сеть недоступна (попытка %s/3), повтор через 10 с: %s", attempt, e)
                await asyncio.sleep(10)
            else:
                logger.error("Не удалось подключиться к Telegram. Проверьте интернет/VPN.")
                await ctx.db.close()
                await bot.session.close()
                return

    try:
        await dp.start_polling(bot)
    finally:
        await ctx.db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

