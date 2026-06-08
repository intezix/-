from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta

import asyncpg


TEST_TELEGRAM_USER_ID = 999000111


async def _main() -> None:
    dsn = (os.getenv("POSTGRES_DSN") or "").strip()
    if not dsn:
        raise RuntimeError("POSTGRES_DSN is required")

    conn = await asyncpg.connect(dsn=dsn)
    try:
        # Ensure user
        user_row = await conn.fetchrow("SELECT id FROM pb_users WHERE telegram_user_id=$1", TEST_TELEGRAM_USER_ID)
        if not user_row:
            user_row = await conn.fetchrow(
                """
                INSERT INTO pb_users (telegram_user_id, username, email)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                TEST_TELEGRAM_USER_ID,
                "test_user",
                "test_user@mail.ru",
            )
        user_id = int(user_row["id"])

        # Payment row
        payment_id = f"test_payment_{int(datetime.now(tz=UTC).timestamp())}"
        raw = {"id": payment_id, "status": "succeeded", "amount": {"value": "590.00", "currency": "RUB"}, "metadata": {"telegram_user_id": str(TEST_TELEGRAM_USER_ID)}}
        await conn.execute(
            """
            INSERT INTO pb_payments (
              user_id, payment_id, idempotence_key, amount, currency, status, is_recurring,
              raw_response_json, processed_at, created_at, updated_at
            )
            VALUES ($1, $2, $3, 590.00, 'RUB', 'succeeded', false, $4::jsonb, NOW(), NOW(), NOW())
            ON CONFLICT (payment_id) DO NOTHING
            """,
            user_id,
            payment_id,
            payment_id + "_idem",
            json.dumps(raw),
        )

        # Subscription
        from pp_common.lifetime_access import lifetime_paid_until

        paid_until = lifetime_paid_until()
        await conn.execute(
            """
            INSERT INTO pb_subscriptions (user_id, status, paid_until, auto_renew_enabled, last_payment_id)
            VALUES ($1, 'active', $2, false, $3)
            ON CONFLICT (user_id) DO UPDATE SET
              status='active',
              paid_until=EXCLUDED.paid_until,
              auto_renew_enabled=false,
              last_payment_id=EXCLUDED.last_payment_id,
              updated_at=NOW()
            """,
            user_id,
            paid_until,
            payment_id,
        )

        print(f"OK: seeded test user telegram_user_id={TEST_TELEGRAM_USER_ID} payment_id={payment_id}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_main())

