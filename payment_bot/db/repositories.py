from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import asyncpg


class UserRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def upsert_user(self, telegram_user_id: int, username: str | None) -> int:
        row = await self.conn.fetchrow(
            """
            INSERT INTO pb_users (telegram_user_id, username)
            VALUES ($1, $2)
            ON CONFLICT (telegram_user_id)
            DO UPDATE SET username = EXCLUDED.username, updated_at = NOW()
            RETURNING id
            """,
            telegram_user_id,
            username,
        )
        return int(row["id"])

    async def set_email(self, telegram_user_id: int, email: str) -> None:
        await self.conn.execute(
            """
            UPDATE pb_users
            SET email = $2, updated_at = NOW()
            WHERE telegram_user_id = $1
            """,
            telegram_user_id,
            email.lower(),
        )

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
            "SELECT * FROM pb_users WHERE telegram_user_id = $1",
            telegram_user_id,
        )

    async def get_preview_pdf_sent(self, telegram_user_id: int) -> bool:
        try:
            row = await self.conn.fetchrow(
                "SELECT preview_pdf_sent FROM pb_users WHERE telegram_user_id = $1",
                telegram_user_id,
            )
        except Exception:
            return False
        if not row:
            return False
        return bool(row["preview_pdf_sent"])

    async def set_preview_pdf_sent(self, telegram_user_id: int, sent: bool = True) -> None:
        try:
            await self.conn.execute(
                """
                UPDATE pb_users
                SET preview_pdf_sent = $2, updated_at = NOW()
                WHERE telegram_user_id = $1
                """,
                telegram_user_id,
                sent,
            )
        except Exception:
            return

    async def get_user_by_username(self, username: str) -> asyncpg.Record | None:
        uname = (username or "").strip().lstrip("@")
        if not uname:
            return None
        return await self.conn.fetchrow(
            "SELECT * FROM pb_users WHERE lower(username) = lower($1)",
            uname,
        )

    async def get_admin_test_override(self, telegram_user_id: int) -> str | None:
        """
        Читает тест-режим из adm_user_overrides (таблица создаётся admin_bot).
        Возвращает режим ('no_sub', 'active', 'expired', 'canceled', 'pending',
        'failed') или None если override не задан/истёк.
        """
        try:
            row = await self.conn.fetchrow(
                """
                SELECT mode FROM adm_user_overrides
                WHERE telegram_user_id = $1
                  AND (expires_at IS NULL OR expires_at > NOW())
                """,
                telegram_user_id,
            )
            return str(row["mode"]) if row else None
        except Exception:
            # Таблица может отсутствовать в dev-окружении — не ломаем бота
            return None


class PaymentRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def find_recent_pending_payment(self, user_id: int, ttl_minutes: int) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
            """
            SELECT *
            FROM pb_payments
            WHERE user_id = $1
              AND status = 'pending'
              AND created_at >= NOW() - ($2 * INTERVAL '1 minute')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
            ttl_minutes,
        )

    async def create_payment_row(
        self,
        user_id: int,
        payment_id: str,
        amount: Decimal,
        currency: str,
        status: str,
        raw_response: dict[str, Any],
        idempotence_key: str,
        is_recurring: bool = False,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO pb_payments (
              user_id, payment_id, amount, currency, status, is_recurring,
              raw_response_json, idempotence_key
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
            ON CONFLICT (payment_id)
            DO UPDATE SET
              status = EXCLUDED.status,
              raw_response_json = EXCLUDED.raw_response_json,
              updated_at = NOW()
            """,
            user_id,
            payment_id,
            amount,
            currency,
            status,
            is_recurring,
            json.dumps(raw_response),
            idempotence_key,
        )

    async def get_payment_by_payment_id(self, payment_id: str) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
            "SELECT * FROM pb_payments WHERE payment_id = $1",
            payment_id,
        )

    async def lock_payment_row(self, payment_id: str) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
            "SELECT * FROM pb_payments WHERE payment_id = $1 FOR UPDATE",
            payment_id,
        )

    async def update_payment_status(
        self,
        payment_id: str,
        status: str,
        raw_response: dict[str, Any],
        payment_method_id: str | None,
        cancel_reason: str | None,
    ) -> None:
        await self.conn.execute(
            """
            UPDATE pb_payments
            SET status = $2::varchar,
                raw_response_json = $3::jsonb,
                payment_method_id = COALESCE($4, payment_method_id),
                cancel_reason = $5,
                refunded_at = CASE WHEN $2::varchar = 'refunded' THEN NOW() ELSE refunded_at END,
                updated_at = NOW()
            WHERE payment_id = $1
            """,
            payment_id,
            status,
            json.dumps(raw_response),
            payment_method_id,
            cancel_reason,
        )

    async def mark_processed(self, payment_id: str) -> bool:
        result = await self.conn.execute(
            """
            UPDATE pb_payments
            SET processed_at = NOW(), updated_at = NOW()
            WHERE payment_id = $1 AND processed_at IS NULL
            """,
            payment_id,
        )
        return result.endswith("1")

    async def mark_admin_notified(self, payment_id: str) -> None:
        await self.conn.execute(
            "UPDATE pb_payments SET admin_notified_at = NOW(), updated_at = NOW() WHERE payment_id = $1",
            payment_id,
        )


class SubscriptionRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def activate_subscription(
        self,
        user_id: int,
        payment_id: str,
    ) -> asyncpg.Record:
        from pp_common.lifetime_access import lifetime_paid_until

        paid_until = lifetime_paid_until()
        row = await self.conn.fetchrow(
            """
            INSERT INTO pb_subscriptions (
              user_id, status, paid_until, auto_renew_enabled, last_payment_id, payment_method_id
            )
            VALUES ($1, 'active', $2, false, $3, NULL)
            ON CONFLICT (user_id)
            DO UPDATE SET
              status = 'active',
              paid_until = $2,
              auto_renew_enabled = false,
              canceled_at = NULL,
              revoke_source = NULL,
              last_payment_id = EXCLUDED.last_payment_id,
              payment_method_id = NULL,
              updated_at = NOW()
            RETURNING *
            """,
            user_id,
            paid_until,
            payment_id,
        )
        return row

    async def get_by_user_id(self, user_id: int) -> asyncpg.Record | None:
        return await self.conn.fetchrow("SELECT * FROM pb_subscriptions WHERE user_id = $1", user_id)

    async def disable_auto_renew(self, user_id: int, revoke_source: str) -> bool:
        result = await self.conn.execute(
            """
            UPDATE pb_subscriptions
            SET auto_renew_enabled = false,
                payment_method_id = NULL,
                revoke_source = $2,
                updated_at = NOW()
            WHERE user_id = $1
            """,
            user_id,
            revoke_source,
        )
        return result.endswith("1")

    async def cancel_subscription(self, user_id: int, revoke_source: str) -> bool:
        result = await self.conn.execute(
            """
            UPDATE pb_subscriptions
            SET auto_renew_enabled = false,
                canceled_at = NOW(),
                payment_method_id = NULL,
                revoke_source = $2,
                updated_at = NOW()
            WHERE user_id = $1
              AND canceled_at IS NULL
            """,
            user_id,
            revoke_source,
        )
        return result.endswith("1")

    async def manual_grant(self, user_id: int, days: int, revoke_source: str) -> asyncpg.Record:
        """Admin grant: always lifetime access (days arg kept for API compatibility)."""
        del days
        from pp_common.lifetime_access import lifetime_paid_until

        paid_until = lifetime_paid_until()
        row = await self.conn.fetchrow(
            """
            INSERT INTO pb_subscriptions (
              user_id, status, paid_until, auto_renew_enabled, canceled_at, revoke_source, last_payment_id, payment_method_id
            )
            VALUES ($1, 'active', $2, false, NULL, $3, NULL, NULL)
            ON CONFLICT (user_id)
            DO UPDATE SET
              status = 'active',
              paid_until = $2,
              auto_renew_enabled = false,
              canceled_at = NULL,
              revoke_source = $3,
              payment_method_id = NULL,
              updated_at = NOW()
            RETURNING *
            """,
            user_id,
            paid_until,
            revoke_source,
        )
        return row

    async def manual_revoke(self, user_id: int, revoke_source: str) -> bool:
        result = await self.conn.execute(
            """
            UPDATE pb_subscriptions
            SET status = 'inactive',
                paid_until = NOW(),
                auto_renew_enabled = false,
                payment_method_id = NULL,
                canceled_at = COALESCE(canceled_at, NOW()),
                revoke_source = $2,
                updated_at = NOW()
            WHERE user_id = $1
            """,
            user_id,
            revoke_source,
        )
        return result.endswith("1")

    async def list_due_for_renew(self, limit: int = 200) -> list[asyncpg.Record]:
        return await self.conn.fetch(
            """
            SELECT s.*, u.telegram_user_id, u.email, u.username
            FROM pb_subscriptions s
            JOIN pb_users u ON u.id = s.user_id
            WHERE s.status = 'active'
              AND s.auto_renew_enabled = true
              AND s.payment_method_id IS NOT NULL
              AND s.paid_until <= NOW() + interval '1 day'
            ORDER BY s.paid_until ASC
            LIMIT $1
            """,
            limit,
        )


class EventRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def log_event(self, user_id: int | None, event_type: str, payload: dict[str, Any]) -> None:
        await self.conn.execute(
            """
            INSERT INTO pb_events (user_id, event_type, payload_json)
            VALUES ($1, $2, $3::jsonb)
            """,
            user_id,
            event_type,
            json.dumps(payload),
        )


class OutboxRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def enqueue_once(
        self,
        event_type: str,
        dedupe_key: str,
        payload: dict[str, Any],
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO pb_notification_outbox (event_type, dedupe_key, payload_json, status)
            VALUES ($1, $2, $3::jsonb, 'pending')
            ON CONFLICT (dedupe_key) DO NOTHING
            """,
            event_type,
            dedupe_key,
            json.dumps(payload),
        )

    async def fetch_batch_for_send(self, limit: int = 50) -> list[asyncpg.Record]:
        return await self.conn.fetch(
            """
            SELECT *
            FROM pb_notification_outbox
            WHERE status IN ('pending', 'retry')
              AND (next_retry_at IS NULL OR next_retry_at <= NOW())
            ORDER BY created_at ASC
            LIMIT $1
            """,
            limit,
        )

    async def mark_sent(self, outbox_id: int) -> None:
        await self.conn.execute(
            """
            UPDATE pb_notification_outbox
            SET status = 'sent', sent_at = NOW(), updated_at = NOW()
            WHERE id = $1
            """,
            outbox_id,
        )

    async def mark_retry(self, outbox_id: int, error_message: str, attempt_count: int) -> None:
        delay_seconds = min(300, 2 ** min(attempt_count, 7))
        await self.conn.execute(
            """
            UPDATE pb_notification_outbox
            SET status = 'retry',
                last_error = $2,
                attempt_count = attempt_count + 1,
                next_retry_at = NOW() + ($3 || ' seconds')::interval,
                updated_at = NOW()
            WHERE id = $1
            """,
            outbox_id,
            error_message[:1000],
            delay_seconds,
        )


class RecurringAttemptRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def create_attempt(
        self,
        subscription_id: int,
        status: str,
        payment_id: str | None,
        error_message: str | None,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO pb_recurring_attempts (subscription_id, status, payment_id, error_message)
            VALUES ($1, $2, $3, $4)
            """,
            subscription_id,
            status,
            payment_id,
            error_message,
        )

