from __future__ import annotations

import logging

from aiogram import Bot

from admin_bot.app_context import AppContext


logger = logging.getLogger(__name__)


async def send_health_report_job(bot: Bot, ctx: AppContext) -> None:
    try:
        text = await ctx.health.build_health_report()
        await ctx.alerts.send_health_report(bot=bot, text=text)
    except Exception as e:
        logger.exception("Health report job failed: %s", e)

