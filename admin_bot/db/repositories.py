from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import asyncpg


class AdminUserRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def upsert_owner(self, telegram_user_id: int, username: str | None) -> None:
        await self.conn.execute(
            """
            INSERT INTO adm_admin_users (telegram_user_id, username, role, is_active)
            VALUES ($1, $2, 'owner', true)
            ON CONFLICT (telegram_user_id) DO UPDATE SET
              username = EXCLUDED.username,
              role = 'owner',
              is_active = true
            """,
            telegram_user_id,
            (username or "").lstrip("@") or None,
        )

    async def get_by_telegram_id(self, telegram_user_id: int) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
            "SELECT * FROM adm_admin_users WHERE telegram_user_id = $1",
            telegram_user_id,
        )

    async def list_notifiable_admins(self, *, notify_kind: str) -> list[asyncpg.Record]:
        if notify_kind not in {"errors", "health"}:
            raise ValueError("notify_kind must be 'errors' or 'health'")
        column = "notify_errors" if notify_kind == "errors" else "notify_health"
        return await self.conn.fetch(
            f"""
            SELECT *
            FROM adm_admin_users
            WHERE is_active = true
              AND notify_enabled = true
              AND {column} = true
            ORDER BY role = 'owner' DESC, telegram_user_id ASC
            """
        )

    async def list_admins(self) -> list[asyncpg.Record]:
        return await self.conn.fetch(
            """
            SELECT *
            FROM adm_admin_users
            ORDER BY role = 'owner' DESC, is_active DESC, telegram_user_id ASC
            """
        )

    async def create_admin(
        self,
        telegram_user_id: int,
        username: str | None,
        role: str,
        created_by: int,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO adm_admin_users (telegram_user_id, username, role, is_active, created_by)
            VALUES ($1, $2, $3, true, $4)
            ON CONFLICT (telegram_user_id) DO UPDATE SET
              username = EXCLUDED.username,
              role = EXCLUDED.role,
              is_active = true,
              created_by = EXCLUDED.created_by
            """,
            telegram_user_id,
            (username or "").lstrip("@") or None,
            role,
            created_by,
        )

    async def set_active(self, telegram_user_id: int, is_active: bool) -> None:
        await self.conn.execute(
            "UPDATE adm_admin_users SET is_active = $2 WHERE telegram_user_id = $1",
            telegram_user_id,
            is_active,
        )

    async def set_role(self, telegram_user_id: int, role: str) -> None:
        await self.conn.execute(
            "UPDATE adm_admin_users SET role = $2 WHERE telegram_user_id = $1",
            telegram_user_id,
            role,
        )

    async def set_notify_flags(
        self,
        telegram_user_id: int,
        *,
        notify_enabled: bool | None = None,
        notify_errors: bool | None = None,
        notify_health: bool | None = None,
    ) -> None:
        await self.conn.execute(
            """
            UPDATE adm_admin_users
            SET notify_enabled = COALESCE($2, notify_enabled),
                notify_errors = COALESCE($3, notify_errors),
                notify_health = COALESCE($4, notify_health)
            WHERE telegram_user_id = $1
            """,
            telegram_user_id,
            notify_enabled,
            notify_errors,
            notify_health,
        )


class AdminActionRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def log_action(
        self,
        *,
        admin_telegram_user_id: int,
        target_telegram_user_id: int | None,
        action: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        def _json_default(v: Any):
            # Keep audit logging robust: never fail on datetimes/records.
            if isinstance(v, datetime):
                return v.isoformat()
            return str(v)

        await self.conn.execute(
            """
            INSERT INTO adm_admin_actions (
              admin_telegram_user_id, target_telegram_user_id, action, before_json, after_json
            )
            VALUES ($1, $2, $3, $4::jsonb, $5::jsonb)
            """,
            admin_telegram_user_id,
            target_telegram_user_id,
            action,
            json.dumps(before or {}, default=_json_default),
            json.dumps(after or {}, default=_json_default),
        )


class UserOverrideRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def set_override(
        self,
        *,
        telegram_user_id: int,
        mode: str,
        expires_at: datetime | None,
        created_by: int,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO adm_user_overrides (telegram_user_id, mode, expires_at, created_by)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_user_id) DO UPDATE SET
              mode = EXCLUDED.mode,
              expires_at = EXCLUDED.expires_at,
              created_by = EXCLUDED.created_by,
              created_at = NOW()
            """,
            telegram_user_id,
            mode,
            expires_at,
            created_by,
        )

    async def cleanup_expired(self) -> int:
        res = await self.conn.execute(
            "DELETE FROM adm_user_overrides WHERE expires_at IS NOT NULL AND expires_at <= NOW()"
        )
        # asyncpg returns e.g. 'DELETE 3'
        try:
            return int(str(res).split()[-1])
        except Exception:
            return 0

    async def clear_override(self, telegram_user_id: int) -> None:
        await self.conn.execute(
            "DELETE FROM adm_user_overrides WHERE telegram_user_id = $1",
            telegram_user_id,
        )

    async def get_override(self, telegram_user_id: int) -> asyncpg.Record | None:
        # Enforce auto-expire cleanup to avoid stale overrides.
        await self.cleanup_expired()
        return await self.conn.fetchrow(
            """
            SELECT *
            FROM adm_user_overrides
            WHERE telegram_user_id = $1
              AND (expires_at IS NULL OR expires_at > NOW())
            """,
            telegram_user_id,
        )


class PaymentBotRepository:
    """
    Read/write source-of-truth tables from payment_bot schema (pb_*).
    """

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def find_user_by_telegram_id(self, telegram_user_id: int) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
            "SELECT * FROM pb_users WHERE telegram_user_id = $1",
            telegram_user_id,
        )

    async def find_user_by_username(self, username: str) -> asyncpg.Record | None:
        uname = (username or "").strip().lstrip("@")
        if not uname:
            return None
        return await self.conn.fetchrow(
            "SELECT * FROM pb_users WHERE lower(username) = lower($1)",
            uname,
        )

    async def find_user_by_email(self, email: str) -> asyncpg.Record | None:
        mail = (email or "").strip().lower()
        if not mail:
            return None
        return await self.conn.fetchrow(
            "SELECT * FROM pb_users WHERE lower(email) = lower($1)",
            mail,
        )

    async def get_subscription_by_user_id(self, user_id: int) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
            "SELECT * FROM pb_subscriptions WHERE user_id = $1",
            user_id,
        )

    async def get_last_payment_for_user(self, user_id: int) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
            """
            SELECT *
            FROM pb_payments
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )

    async def list_payments(
        self,
        *,
        status: str | None = None,
        since: datetime | None = None,
        limit: int = 20,
    ) -> list[asyncpg.Record]:
        clauses: list[str] = []
        args: list[Any] = []
        if status:
            clauses.append(f"p.status = ${len(args)+1}")
            args.append(status)
        if since:
            clauses.append(f"p.created_at >= ${len(args)+1}")
            args.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        return await self.conn.fetch(
            f"""
            SELECT p.*, u.telegram_user_id, u.username, u.email
            FROM pb_payments p
            JOIN pb_users u ON u.id = p.user_id
            {where}
            ORDER BY p.created_at DESC
            LIMIT {int(limit)}
            """,
            *args,
        )

    async def list_all_telegram_user_ids(self) -> list[int]:
        """All known user telegram IDs — used for broadcast."""
        rows = await self.conn.fetch(
            "SELECT telegram_user_id FROM pb_users WHERE telegram_user_id IS NOT NULL ORDER BY id ASC"
        )
        return [int(r["telegram_user_id"]) for r in rows]

    async def count_users(self) -> int:
        return int(await self.conn.fetchval("SELECT COUNT(*) FROM pb_users WHERE telegram_user_id IS NOT NULL") or 0)

    async def list_users_page(self, *, offset: int, limit: int = 15) -> list[asyncpg.Record]:
        """Paginated list of users ordered by newest first."""
        return await self.conn.fetch(
            """
            SELECT telegram_user_id, username, email
            FROM pb_users
            WHERE telegram_user_id IS NOT NULL
            ORDER BY id DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )

    async def get_payment_by_payment_id(self, payment_id: str) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
            """
            SELECT p.*, u.telegram_user_id, u.username, u.email
            FROM pb_payments p
            JOIN pb_users u ON u.id = p.user_id
            WHERE p.payment_id = $1
            """,
            payment_id,
        )

    async def manual_grant_subscription(self, *, user_id: int, days: int, revoke_source: str) -> asyncpg.Record:
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

    async def manual_revoke_subscription(self, *, user_id: int, revoke_source: str) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
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
            RETURNING *
            """,
            user_id,
            revoke_source,
        )

    async def disable_auto_renew(self, *, user_id: int, revoke_source: str) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
            """
            UPDATE pb_subscriptions
            SET auto_renew_enabled = false,
                payment_method_id = NULL,
                revoke_source = $2,
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            revoke_source,
        )

    async def restore_auto_renew(self, *, user_id: int, payment_method_id: str, revoke_source: str) -> asyncpg.Record | None:
        return await self.conn.fetchrow(
            """
            UPDATE pb_subscriptions
            SET auto_renew_enabled = true,
                payment_method_id = $2,
                revoke_source = $3,
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            payment_method_id,
            revoke_source,
        )

    async def set_expired(self, *, user_id: int, revoke_source: str) -> asyncpg.Record | None:
        # Set explicit expired status to match admin UX (string status has no strict constraint).
        return await self.conn.fetchrow(
            """
            UPDATE pb_subscriptions
            SET status = 'expired',
                paid_until = NOW(),
                auto_renew_enabled = false,
                payment_method_id = NULL,
                canceled_at = COALESCE(canceled_at, NOW()),
                revoke_source = $2,
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            revoke_source,
        )


class EventRepository:
    """
    Единный event store: pb_events. Все “расширенные поля” храним в payload_json.
    """

    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def log_event(
        self,
        *,
        user_id: int | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO pb_events (user_id, event_type, payload_json)
            VALUES ($1, $2, $3::jsonb)
            """,
            user_id,
            event_type,
            json.dumps(payload),
        )

    async def list_user_events(
        self,
        *,
        telegram_user_id: int,
        limit: int = 20,
        before_id: int | None = None,
        only_errors: bool = False,
        only_payments: bool = False,
        only_buttons: bool = False,
    ) -> list[asyncpg.Record]:
        clauses: list[str] = ["(payload_json->>'telegram_user_id')::bigint = $1"]
        args: list[Any] = [telegram_user_id]
        if before_id is not None:
            clauses.append(f"id < ${len(args)+1}")
            args.append(before_id)
        if only_errors:
            clauses.append("(payload_json->>'status') = 'error'")
        if only_payments:
            clauses.append("(payload_json->>'event_group') = 'payments'")
        if only_buttons:
            clauses.append("(payload_json->>'event_group') = 'buttons'")

        where = " AND ".join(clauses)
        return await self.conn.fetch(
            f"""
            SELECT *
            FROM pb_events
            WHERE {where}
            ORDER BY id DESC
            LIMIT {int(limit)}
            """,
            *args,
        )

    async def list_recent_errors(
        self,
        *,
        limit: int = 20,
        before_id: int | None = None,
    ) -> list[asyncpg.Record]:
        clauses: list[str] = ["(payload_json->>'status') = 'error'"]
        args: list[Any] = []
        if before_id is not None:
            clauses.append("id < $1")
            args.append(before_id)
        where = " AND ".join(clauses)
        return await self.conn.fetch(
            f"""
            SELECT *
            FROM pb_events
            WHERE {where}
            ORDER BY id DESC
            LIMIT {int(limit)}
            """,
            *args,
        )

    async def list_unnotified_errors(self, *, limit: int = 20) -> list[asyncpg.Record]:
        return await self.conn.fetch(
            f"""
            SELECT *
            FROM pb_events
            WHERE (payload_json->>'status') = 'error'
              AND COALESCE(payload_json->>'admin_notified', 'false') != 'true'
            ORDER BY id ASC
            LIMIT {int(limit)}
            """
        )

    async def get_event(self, event_id: int) -> asyncpg.Record | None:
        return await self.conn.fetchrow("SELECT * FROM pb_events WHERE id = $1", event_id)

    async def mark_resolved(self, event_id: int, resolver_id: int) -> None:
        # Keep a small, explicit marker inside payload_json
        await self.conn.execute(
            """
            UPDATE pb_events
            SET payload_json = jsonb_set(
              jsonb_set(payload_json, '{resolved}', 'true'::jsonb, true),
              '{resolved_by}', to_jsonb($2::bigint), true
            )
            WHERE id = $1
            """,
            event_id,
            resolver_id,
        )

    async def mark_admin_notified(self, event_id: int) -> None:
        await self.conn.execute(
            """
            UPDATE pb_events
            SET payload_json = jsonb_set(payload_json, '{admin_notified}', 'true'::jsonb, true)
            WHERE id = $1
            """,
            event_id,
        )


class AlertDedupRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    async def should_send(self, *, fingerprint: str, cooldown_seconds: int) -> bool:
        row = await self.conn.fetchrow(
            """
            SELECT last_sent_at
            FROM adm_alert_dedup
            WHERE fingerprint = $1
            """,
            fingerprint,
        )
        if not row:
            return True
        last = row["last_sent_at"]
        if not last:
            return True
        seconds = (now_utc() - last).total_seconds()
        return seconds >= cooldown_seconds

    async def mark_sent(self, *, fingerprint: str) -> None:
        await self.conn.execute(
            """
            INSERT INTO adm_alert_dedup (fingerprint, last_sent_at)
            VALUES ($1, NOW())
            ON CONFLICT (fingerprint) DO UPDATE SET
              last_sent_at = NOW()
            """,
            fingerprint,
        )


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class Money:
    amount: str
    currency: str

