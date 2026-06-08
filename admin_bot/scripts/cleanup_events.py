from __future__ import annotations

import asyncio
import os

import asyncpg


async def _main() -> None:
    dsn = (os.getenv("POSTGRES_DSN") or "").strip()
    if not dsn:
        raise RuntimeError("POSTGRES_DSN is required")
    days = int((os.getenv("PB_EVENTS_TTL_DAYS") or "60").strip())
    conn = await asyncpg.connect(dsn=dsn)
    try:
        res = await conn.execute(
            "DELETE FROM pb_events WHERE created_at < NOW() - ($1 * INTERVAL '1 day')",
            days,
        )
        print(f"OK: {res} (ttl_days={days})")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_main())

