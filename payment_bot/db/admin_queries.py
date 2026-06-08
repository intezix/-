from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg


class AdminRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    # ─────────────────────────── ROLES ────────────────────────────

    async def ensure_roles_table(self) -> None:
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pb_admin_roles (
                telegram_user_id BIGINT PRIMARY KEY,
                role             VARCHAR NOT NULL DEFAULT 'viewer',
                added_by         BIGINT,
                created_at       TIMESTAMPTZ DEFAULT NOW()
            )
        """)

    async def get_all_roles(self) -> list[asyncpg.Record]:
        return await self.conn.fetch(
            """SELECT r.*, u.username
               FROM pb_admin_roles r
               LEFT JOIN pb_users u ON u.telegram_user_id = r.telegram_user_id
               ORDER BY r.role, r.created_at"""
        )

    async def get_role(self, telegram_user_id: int) -> str | None:
        row = await self.conn.fetchrow(
            "SELECT role FROM pb_admin_roles WHERE telegram_user_id = $1",
            telegram_user_id,
        )
        return row["role"] if row else None

    async def set_role(self, telegram_user_id: int, role: str, added_by: int) -> None:
        await self.conn.execute(
            """INSERT INTO pb_admin_roles (telegram_user_id, role, added_by)
               VALUES ($1, $2, $3)
               ON CONFLICT (telegram_user_id) DO UPDATE
               SET role = EXCLUDED.role, added_by = EXCLUDED.added_by""",
            telegram_user_id,
            role,
            added_by,
        )

    async def remove_role(self, telegram_user_id: int) -> bool:
        result = await self.conn.execute(
            "DELETE FROM pb_admin_roles WHERE telegram_user_id = $1",
            telegram_user_id,
        )
        return result.endswith("1")

    # ─────────────────────────── USERS ────────────────────────────

    async def search_users(self, query: str) -> list[asyncpg.Record]:
        q = query.strip().lstrip("@")
        if q.lstrip("-").isdigit():
            rows = await self.conn.fetch(
                """SELECT u.*, s.status AS sub_status, s.paid_until, s.auto_renew_enabled, s.canceled_at
                   FROM pb_users u LEFT JOIN pb_subscriptions s ON s.user_id = u.id
                   WHERE u.telegram_user_id = $1""",
                int(q),
            )
            if rows:
                return list(rows)
        rows = await self.conn.fetch(
            """SELECT u.*, s.status AS sub_status, s.paid_until, s.auto_renew_enabled, s.canceled_at
               FROM pb_users u LEFT JOIN pb_subscriptions s ON s.user_id = u.id
               WHERE lower(u.username) = lower($1) OR lower(u.email) LIKE lower($2)
               LIMIT 10""",
            q,
            f"%{q}%",
        )
        return list(rows)

    async def get_recent_users(self, limit: int = 10) -> list[asyncpg.Record]:
        return await self.conn.fetch(
            """SELECT u.*, s.status AS sub_status, s.paid_until
               FROM pb_users u LEFT JOIN pb_subscriptions s ON s.user_id = u.id
               ORDER BY u.created_at DESC LIMIT $1""",
            limit,
        )

    async def get_user_full(self, db_user_id: int) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
            """SELECT u.*, s.status AS sub_status, s.paid_until, s.auto_renew_enabled,
                      s.canceled_at, s.payment_method_id, s.revoke_source,
                      (SELECT COUNT(*) FROM pb_payments WHERE user_id = u.id) AS payments_total,
                      (SELECT COUNT(*) FROM pb_payments WHERE user_id = u.id AND status = 'succeeded') AS payments_ok
               FROM pb_users u LEFT JOIN pb_subscriptions s ON s.user_id = u.id
               WHERE u.id = $1""",
            db_user_id,
        )

    async def get_user_payments(self, db_user_id: int, limit: int = 5) -> list[asyncpg.Record]:
        return await self.conn.fetch(
            "SELECT * FROM pb_payments WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            db_user_id,
            limit,
        )

    async def get_user_events(self, db_user_id: int, limit: int = 10) -> list[asyncpg.Record]:
        return await self.conn.fetch(
            "SELECT * FROM pb_events WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            db_user_id,
            limit,
        )

    # ─────────────────────── SUBSCRIPTIONS ────────────────────────

    async def get_subscriptions_active(self, offset: int, limit: int = 5) -> tuple[list, int]:
        total = await self.conn.fetchval(
            "SELECT COUNT(*) FROM pb_subscriptions WHERE status='active' AND paid_until > NOW()"
        )
        rows = await self.conn.fetch(
            """SELECT s.*, u.telegram_user_id, u.username, u.email
               FROM pb_subscriptions s JOIN pb_users u ON u.id = s.user_id
               WHERE s.status='active' AND s.paid_until > NOW()
               ORDER BY s.paid_until DESC OFFSET $1 LIMIT $2""",
            offset,
            limit,
        )
        return list(rows), int(total)

    async def get_subscriptions_expired(self, offset: int, limit: int = 5) -> tuple[list, int]:
        total = await self.conn.fetchval(
            """SELECT COUNT(*) FROM pb_subscriptions
               WHERE status='inactive' OR (status='active' AND paid_until <= NOW())"""
        )
        rows = await self.conn.fetch(
            """SELECT s.*, u.telegram_user_id, u.username, u.email
               FROM pb_subscriptions s JOIN pb_users u ON u.id = s.user_id
               WHERE s.status='inactive' OR (s.status='active' AND s.paid_until <= NOW())
               ORDER BY s.updated_at DESC OFFSET $1 LIMIT $2""",
            offset,
            limit,
        )
        return list(rows), int(total)

    async def get_subscriptions_cancelled(self, offset: int, limit: int = 5) -> tuple[list, int]:
        total = await self.conn.fetchval(
            "SELECT COUNT(*) FROM pb_subscriptions WHERE canceled_at IS NOT NULL"
        )
        rows = await self.conn.fetch(
            """SELECT s.*, u.telegram_user_id, u.username, u.email
               FROM pb_subscriptions s JOIN pb_users u ON u.id = s.user_id
               WHERE s.canceled_at IS NOT NULL
               ORDER BY s.canceled_at DESC OFFSET $1 LIMIT $2""",
            offset,
            limit,
        )
        return list(rows), int(total)

    # ────────────────────────── PAYMENTS ──────────────────────────

    async def get_payments_by_status(
        self, status: str, offset: int, limit: int = 5
    ) -> tuple[list, int]:
        if status == "failed":
            where = "p.status IN ('cancelled', 'failed')"
        else:
            where = f"p.status = '{status}'"
        total = await self.conn.fetchval(f"SELECT COUNT(*) FROM pb_payments p WHERE {where}")
        rows = await self.conn.fetch(
            f"""SELECT p.*, u.telegram_user_id, u.username, u.email
                FROM pb_payments p JOIN pb_users u ON u.id = p.user_id
                WHERE {where}
                ORDER BY p.created_at DESC OFFSET $1 LIMIT $2""",
            offset,
            limit,
        )
        return list(rows), int(total)

    # ──────────────────────── STATISTICS ──────────────────────────

    async def get_stats(self, days: int) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=days)

        total_users = await self.conn.fetchval("SELECT COUNT(*) FROM pb_users")
        users_new = await self.conn.fetchval(
            "SELECT COUNT(*) FROM pb_users WHERE created_at >= $1", since
        )
        subs_active = await self.conn.fetchval(
            "SELECT COUNT(*) FROM pb_subscriptions WHERE status='active' AND paid_until > NOW()"
        )
        subs_new = await self.conn.fetchval(
            "SELECT COUNT(*) FROM pb_subscriptions WHERE created_at >= $1", since
        )
        subs_cancelled = await self.conn.fetchval(
            "SELECT COUNT(*) FROM pb_subscriptions WHERE canceled_at >= $1", since
        )
        payments_count = await self.conn.fetchval(
            "SELECT COUNT(*) FROM pb_payments WHERE status='succeeded' AND created_at >= $1", since
        )
        payments_revenue = await self.conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM pb_payments WHERE status='succeeded' AND created_at >= $1",
            since,
        )
        errors_count = await self.conn.fetchval(
            "SELECT COUNT(*) FROM pb_events WHERE event_type LIKE 'error%' AND created_at >= $1",
            since,
        )
        auto_renew_active = await self.conn.fetchval(
            """SELECT COUNT(*) FROM pb_subscriptions
               WHERE status='active' AND paid_until > NOW() AND auto_renew_enabled = true"""
        )

        conversion = 0.0
        if users_new and int(users_new) > 0:
            conversion = round(int(payments_count) / int(users_new) * 100, 1)

        return {
            "period_days": days,
            "total_users": int(total_users or 0),
            "users_new": int(users_new or 0),
            "subs_active": int(subs_active or 0),
            "auto_renew_active": int(auto_renew_active or 0),
            "subs_new": int(subs_new or 0),
            "subs_cancelled": int(subs_cancelled or 0),
            "payments_count": int(payments_count or 0),
            "payments_revenue": float(payments_revenue or 0),
            "conversion": conversion,
            "errors_count": int(errors_count or 0),
        }

    # ──────────────────────────── LOGS ────────────────────────────

    async def get_recent_events(
        self, limit: int = 20, db_user_id: int | None = None
    ) -> list[asyncpg.Record]:
        if db_user_id:
            return await self.conn.fetch(
                """SELECT e.*, u.telegram_user_id, u.username
                   FROM pb_events e LEFT JOIN pb_users u ON u.id = e.user_id
                   WHERE e.user_id = $1
                   ORDER BY e.created_at DESC LIMIT $2""",
                db_user_id,
                limit,
            )
        return await self.conn.fetch(
            """SELECT e.*, u.telegram_user_id, u.username
               FROM pb_events e LEFT JOIN pb_users u ON u.id = e.user_id
               ORDER BY e.created_at DESC LIMIT $1""",
            limit,
        )

    # ───────────────────────── MONITORING ─────────────────────────

    async def get_monitoring_info(self) -> dict[str, Any]:
        outbox_pending = await self.conn.fetchval(
            "SELECT COUNT(*) FROM pb_notification_outbox WHERE status = 'pending'"
        )
        outbox_retry = await self.conn.fetchval(
            "SELECT COUNT(*) FROM pb_notification_outbox WHERE status = 'retry'"
        )
        outbox_failed = await self.conn.fetchval(
            "SELECT COUNT(*) FROM pb_notification_outbox WHERE status = 'failed'"
        )
        recent_errors = await self.conn.fetch(
            """SELECT event_type, payload_json::text, created_at
               FROM pb_events
               WHERE event_type LIKE 'error%'
               ORDER BY created_at DESC LIMIT 5"""
        )
        return {
            "outbox_pending": int(outbox_pending or 0),
            "outbox_retry": int(outbox_retry or 0),
            "outbox_failed": int(outbox_failed or 0),
            "recent_errors": list(recent_errors),
        }

    # ─────────────────────── TEST MODES ───────────────────────────

    async def test_set_active(self, db_user_id: int, days: int = 30) -> None:
        await self.conn.execute(
            """INSERT INTO pb_subscriptions (user_id, status, paid_until, auto_renew_enabled)
               VALUES ($1, 'active', NOW() + ($2 * INTERVAL '1 day'), true)
               ON CONFLICT (user_id) DO UPDATE SET
                 status = 'active',
                 paid_until = NOW() + ($2 * INTERVAL '1 day'),
                 auto_renew_enabled = true,
                 canceled_at = NULL,
                 revoke_source = 'admin_test',
                 updated_at = NOW()""",
            db_user_id,
            days,
        )

    async def test_set_expired(self, db_user_id: int) -> None:
        await self.conn.execute(
            """INSERT INTO pb_subscriptions (user_id, status, paid_until, auto_renew_enabled)
               VALUES ($1, 'active', NOW() - INTERVAL '1 hour', false)
               ON CONFLICT (user_id) DO UPDATE SET
                 paid_until = NOW() - INTERVAL '1 hour',
                 auto_renew_enabled = false,
                 revoke_source = 'admin_test',
                 updated_at = NOW()""",
            db_user_id,
        )

    async def test_set_nosub(self, db_user_id: int) -> None:
        await self.conn.execute(
            "DELETE FROM pb_subscriptions WHERE user_id = $1", db_user_id
        )

    async def test_set_norenew(self, db_user_id: int) -> None:
        await self.conn.execute(
            """UPDATE pb_subscriptions
               SET auto_renew_enabled = false, payment_method_id = NULL,
                   revoke_source = 'admin_test', updated_at = NOW()
               WHERE user_id = $1""",
            db_user_id,
        )

    async def test_set_canceled(self, db_user_id: int) -> None:
        await self.conn.execute(
            """UPDATE pb_subscriptions
               SET canceled_at = NOW(), auto_renew_enabled = false,
                   payment_method_id = NULL, revoke_source = 'admin_test', updated_at = NOW()
               WHERE user_id = $1""",
            db_user_id,
        )

    async def test_add_pending_payment(self, db_user_id: int) -> None:
        fake_id = f"test_{uuid.uuid4().hex[:12]}"
        await self.conn.execute(
            """INSERT INTO pb_payments
               (user_id, payment_id, amount, currency, status, is_recurring, idempotence_key)
               VALUES ($1, $2, 590.00, 'RUB', 'pending', false, $2)
               ON CONFLICT (payment_id) DO NOTHING""",
            db_user_id,
            fake_id,
        )
