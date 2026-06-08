from __future__ import annotations

import asyncio

from admin_bot.app_context import build_app_context
from admin_bot.config import load_settings


async def _main() -> None:
    settings = load_settings()
    ctx = await build_app_context(settings)
    try:
        await ctx.roles.ensure_owner_seeded(username=None)
        print("OK: owner seeded in adm_admin_users")
    finally:
        await ctx.db.close()


if __name__ == "__main__":
    asyncio.run(_main())

