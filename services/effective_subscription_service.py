from __future__ import annotations

import logging
import os

import asyncpg

from pp_common.effective_subscription import EffectiveSubscriptionState, get_effective_subscription_state


logger = logging.getLogger(__name__)

_POOL: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    global _POOL
    if _POOL:
        return _POOL
    dsn = (os.getenv("POSTGRES_DSN") or "").strip()
    if not dsn:
        raise RuntimeError("POSTGRES_DSN is required")
    _POOL = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)
    return _POOL


async def get_effective_state(telegram_user_id: int) -> EffectiveSubscriptionState:
    """
    Async helper for main_bot: queries PostgreSQL and applies admin overrides.
    """
    pool = await _get_pool()
    async with pool.acquire() as conn:
        try:
            return await get_effective_subscription_state(conn, telegram_user_id)
        except asyncpg.UndefinedTableError:
            # In some environments admin tables may be missing; treat as no override.
            logger.warning("adm_user_overrides table missing; falling back to real subscription only")
            # Retry without touching adm_user_overrides.
            sub = await conn.fetchrow(
                """
                SELECT s.status, s.paid_until, s.auto_renew_enabled
                FROM pb_users u
                LEFT JOIN pb_subscriptions s ON s.user_id = u.id
                WHERE u.telegram_user_id = $1
                """,
                int(telegram_user_id),
            )
            # Reuse core mapper via the same function by pretending no override existed.
            # (We can't call private helper; keep logic minimal here.)
            now = __import__("datetime").datetime.now(__import__("datetime").UTC)
            if not sub:
                return {
                    "status": "none",
                    "paid_until": None,
                    "auto_renew": None,
                    "is_override": False,
                    "override_mode": None,
                    "override_expires_at": None,
                }
            paid_until = sub.get("paid_until")
            status = str(sub.get("status") or "inactive")
            auto = sub.get("auto_renew_enabled")
            if status == "active" and paid_until and paid_until > now:
                eff = "active"
            elif paid_until and paid_until <= now:
                eff = "expired"
            else:
                eff = "inactive"
            return {
                "status": eff,  # type: ignore[typeddict-item]
                "paid_until": paid_until,
                "auto_renew": bool(auto) if auto is not None else None,
                "is_override": False,
                "override_mode": None,
                "override_expires_at": None,
            }

