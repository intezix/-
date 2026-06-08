from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from admin_bot.db.database import Database
from admin_bot.db.repositories import PaymentBotRepository
from admin_bot.services.formatting_service import FormattingService
from admin_bot.services.role_service import RoleService


class PaymentService:
    def __init__(self, *, db: Database, roles: RoleService) -> None:
        self._db = db
        self._roles = roles
        self._fmt = FormattingService()

    async def list_payments(self, *, actor_telegram_user_id: int, status: str | None, period: str | None) -> list[dict]:
        role = await self._roles.require_access(actor_telegram_user_id)
        if not self._roles.can_view_payments(role):
            raise PermissionError("Недостаточно прав для просмотра платежей")
        since = None
        if period == "24h":
            since = datetime.now(tz=UTC) - timedelta(hours=24)
        elif period == "7d":
            since = datetime.now(tz=UTC) - timedelta(days=7)
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            pb = PaymentBotRepository(conn)
            rows = await pb.list_payments(status=status, since=since, limit=30)
            return [dict(r) for r in rows]

    async def get_payment_card(self, *, actor_telegram_user_id: int, payment_id: str) -> tuple[str, dict]:
        role = await self._roles.require_access(actor_telegram_user_id)
        if not self._roles.can_view_payments(role):
            raise PermissionError("Недостаточно прав для просмотра платежей")
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            pb = PaymentBotRepository(conn)
            row = await pb.get_payment_by_payment_id(payment_id)
            if not row:
                raise ValueError("Платёж не найден")
            d = dict(row)
            payment_method_saved = bool(d.get("payment_method_id"))
            text = self._fmt.payment_card(
                payment_id=str(d["payment_id"]),
                telegram_user_id=int(d["telegram_user_id"]),
                email=d.get("email"),
                amount=str(d["amount"]),
                currency=str(d["currency"]),
                status=str(d["status"]),
                is_recurring=bool(d.get("is_recurring")),
                payment_method_saved=payment_method_saved,
                admin_notified_at=d.get("admin_notified_at"),
                created_at=d.get("created_at"),
            )
            return text, d

    async def get_raw_payment_json(self, *, actor_telegram_user_id: int, payment_id: str) -> str:
        role = await self._roles.require_access(actor_telegram_user_id)
        if not self._roles.can_view_raw_payments(role):
            raise PermissionError("Raw JSON доступен только владельцу/администратору")
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            pb = PaymentBotRepository(conn)
            row = await pb.get_payment_by_payment_id(payment_id)
            if not row:
                raise ValueError("Платёж не найден")
            raw = row["raw_response_json"]
            # asyncpg returns dict-like JSON already
            raw_text = json.dumps(raw, ensure_ascii=False, indent=2)
            if len(raw_text) > 3800:
                raw_text = raw_text[:3800] + "\n... (обрезано)"
            return f"<pre>{raw_text}</pre>"

