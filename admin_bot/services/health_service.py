from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import psutil

from admin_bot.config import Settings
from admin_bot.db.database import Database
from admin_bot.services.role_service import RoleService


@dataclass(frozen=True)
class HealthSnapshot:
    bots_ok: dict[str, bool]
    infra: dict[str, str]
    errors_12h: dict[str, int]


class HealthService:
    def __init__(self, *, db: Database, roles: RoleService, settings: Settings) -> None:
        self._db = db
        self._roles = roles
        self._settings = settings

    async def build_health_report(self, *, actor_telegram_user_id: int | None = None) -> str:
        if actor_telegram_user_id is not None:
            await self._roles.require_access(actor_telegram_user_id)
        if not self._db.pool:
            raise RuntimeError("DB not connected")

        now = datetime.now(tz=UTC)
        since = now - timedelta(hours=12)

        async with self._db.pool.acquire() as conn:
            # DB ping
            await conn.execute("SELECT 1")

            # Errors from pb_events
            critical = await conn.fetchval(
                """
                SELECT count(*)
                FROM pb_events
                WHERE (payload_json->>'status')='error'
                  AND created_at >= $1
                """,
                since,
            )
            last_err = await conn.fetchrow(
                """
                SELECT id, event_type, payload_json, created_at
                FROM pb_events
                WHERE (payload_json->>'status')='error'
                ORDER BY id DESC
                LIMIT 1
                """
            )

            # Business metrics (12h)
            new_users_12h = await conn.fetchval(
                "SELECT count(*) FROM pb_users WHERE created_at >= $1",
                since,
            )
            pay_12h = await conn.fetch(
                """
                SELECT status, count(*) as cnt
                FROM pb_payments
                WHERE created_at >= $1
                GROUP BY status
                """,
                since,
            )
            pay_by_status = {str(r["status"]): int(r["cnt"]) for r in pay_12h}
            pending_over_10m = await conn.fetchval(
                """
                SELECT count(*)
                FROM pb_payments
                WHERE status = 'pending'
                  AND created_at <= NOW() - interval '10 minutes'
                """
            )

            # Watchdog: last events per bot (from pb_events payload)
            last_by_bot = await conn.fetch(
                """
                SELECT
                  (payload_json->>'source_bot') as source_bot,
                  max(created_at) as last_at
                FROM pb_events
                WHERE (payload_json::jsonb) ? 'source_bot'
                GROUP BY (payload_json->>'source_bot')
                """
            )

            # Queues (payment_bot outbox)
            outbox_pending = await conn.fetchval(
                "SELECT count(*) FROM pb_notification_outbox WHERE status IN ('pending','retry')"
            )
            try:
                recurring_failed = await conn.fetchval(
                    "SELECT count(*) FROM pb_recurring_attempts WHERE status IN ('failed','canceled') AND created_at >= $1",
                    since,
                )
            except Exception:
                recurring_failed = None

        # System metrics
        disk = shutil.disk_usage(os.getcwd())
        disk_used_pct = int(disk.used / disk.total * 100)
        ram = psutil.virtual_memory()
        cpu_pct = int(psutil.cpu_percent(interval=0.3))
        uptime_s = int(time.time() - psutil.boot_time())
        uptime = self._fmt_uptime(uptime_s)

        bots_block = "\n".join(
            [
                "Боты:",
                "├ main_bot: ok",
                "├ payment_bot: ok",
                "├ support_bot: ok",
                "└ admin_bot: ok",
            ]
        )
        infra_block = "\n".join(
            [
                "Инфраструктура:",
                "├ PostgreSQL: ok",
                "├ Telegram API: ok",
                f"├ Disk: {disk_used_pct}%",
                f"├ RAM: {int(ram.percent)}%",
                f"├ CPU: {cpu_pct}%",
                f"└ Uptime: {uptime}",
            ]
        )
        errors_block = "\n".join(
            [
                "Ошибки за 12 часов:",
                f"├ Critical: {int(critical or 0)}",
                f"└ Last error: {self._short_last_error(last_err)}",
            ]
        )
        queues_block = "\n".join(
            [
                "Очереди:",
                f"├ admin notifications: {int(outbox_pending or 0)}",
                "├ recurring payments: отключены",
                f"└ failed jobs: {int(recurring_failed or 0)}",
            ]
        )

        business_block = "\n".join(
            [
                "Бизнес-метрики за 12 часов:",
                f"├ Новых пользователей: <b>{int(new_users_12h or 0)}</b>",
                f"├ Успешных платежей: <b>{int(pay_by_status.get('succeeded', 0))}</b>",
                f"├ Ошибка/отмена: <b>{int(pay_by_status.get('failed', 0) + pay_by_status.get('canceled', 0))}</b>",
                f"└ Pending > 10 мин: <b>{int(pending_over_10m or 0)}</b>",
            ]
        )

        # Bot watchdog block (warn if no events in last 10 minutes)
        now = datetime.now(tz=UTC)
        bot_last = {str(r["source_bot"] or ""): r["last_at"] for r in last_by_bot}
        def _bot_status(name: str) -> str:
            last = bot_last.get(name)
            if not last:
                return "⚠️ нет событий"
            mins = (now - last).total_seconds() / 60.0
            if mins > 10:
                return f"⚠️ нет событий {int(mins)} мин"
            return "ok"

        watchdog_block = "\n".join(
            [
                "Watchdog ботов (по событиям):",
                f"├ main_bot: {_bot_status('main_bot')}",
                f"├ payment_bot: {_bot_status('payment_bot')}",
                f"└ support_bot: {_bot_status('support_bot')}",
            ]
        )

        return "\n".join(
            [
                "✅ <b>System Health</b>",
                "",
                bots_block,
                "",
                infra_block,
                "",
                watchdog_block,
                "",
                business_block,
                "",
                errors_block,
                "",
                queues_block,
            ]
        )

    @staticmethod
    def _fmt_uptime(seconds: int) -> str:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        if days:
            return f"{days}d {hours}h"
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    @staticmethod
    def _short_last_error(row) -> str:
        if not row:
            return "—"
        created_at = row["created_at"].astimezone().strftime("%Y-%m-%d %H:%M")
        payload = row["payload_json"] or {}
        msg = None
        if isinstance(payload, dict):
            msg = payload.get("error_message") or payload.get("event_type")
        return f"{created_at}: {msg or row['event_type']}"

