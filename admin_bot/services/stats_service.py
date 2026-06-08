from __future__ import annotations

from datetime import UTC, datetime, timedelta

from admin_bot.db.database import Database
from admin_bot.services.role_service import RoleService


class StatsService:
    def __init__(self, *, db: Database, roles: RoleService) -> None:
        self._db = db
        self._roles = roles

    async def build_stats(self, *, actor_telegram_user_id: int, period: str) -> str:
        role = await self._roles.require_access(actor_telegram_user_id)
        if role not in {"owner", "admin", "viewer", "support"}:
            raise PermissionError("Недостаточно прав")

        if period == "today":
            since = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            title = "📊 Статистика за сегодня"
        elif period == "7d":
            since = datetime.now(tz=UTC) - timedelta(days=7)
            title = "📊 Статистика за 7 дней"
        elif period == "30d":
            since = datetime.now(tz=UTC) - timedelta(days=30)
            title = "📊 Статистика за 30 дней"
        else:
            since = None
            title = "📊 Статистика за всё время"

        if not self._db.pool:
            raise RuntimeError("DB not connected")

        async with self._db.pool.acquire() as conn:
            # Users
            users_where = "WHERE created_at >= $1" if since else ""
            users_cnt = await conn.fetchval(f"SELECT count(*) FROM pb_users {users_where}", *( [since] if since else []))

            # Payments breakdown
            pay_where = "WHERE created_at >= $1" if since else ""
            rows = await conn.fetch(
                f"""
                SELECT status, count(*) as cnt, COALESCE(sum(amount), 0) as sum_amount
                FROM pb_payments
                {pay_where}
                GROUP BY status
                """,
                *( [since] if since else []),
            )
            by_status = {str(r["status"]): int(r["cnt"]) for r in rows}
            revenue = 0
            for r in rows:
                if str(r["status"]) == "succeeded":
                    revenue = float(r["sum_amount"] or 0)
                    break

            # Errors from pb_events payload_json
            err_where = "WHERE (payload_json->>'status')='error'" + (" AND created_at >= $1" if since else "")
            err_cnt = await conn.fetchval(f"SELECT count(*) FROM pb_events {err_where}", *( [since] if since else []))

        succeeded = by_status.get("succeeded", 0)
        pending = by_status.get("pending", 0)
        canceled = by_status.get("canceled", 0) + by_status.get("failed", 0)

        text = "\n".join(
            [
                title,
                "",
                "👥 Пользователи",
                f"├ Новых: <b>{int(users_cnt or 0)}</b>",
                "",
                "💳 Платежи",
                f"├ Успешных: <b>{succeeded}</b>",
                f"├ В обработке: <b>{pending}</b>",
                f"├ Ошибка/отменено: <b>{canceled}</b>",
                f"└ Выручка: <b>{int(revenue)} ₽</b>",
                "",
                "⚠️ Ошибки",
                f"└ Всего: <b>{int(err_cnt or 0)}</b>",
            ]
        )
        return text

