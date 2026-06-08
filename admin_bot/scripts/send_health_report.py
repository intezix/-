from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from admin_bot.app_context import build_app_context
from admin_bot.config import load_settings


async def _main() -> None:
    settings = load_settings()
    ctx = await build_app_context(settings)
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        text = await ctx.health.build_health_report()
        await ctx.alerts.send_health_report(bot=bot, text=text)
        print("OK: health report sent")
    finally:
        await ctx.db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(_main())

