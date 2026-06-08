from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

from admin_bot.db.database import Database
from admin_bot.db.repositories import EventRepository, PaymentBotRepository, UserOverrideRepository
from admin_bot.services.formatting_service import FormattingService
from admin_bot.services.role_service import RoleService


@dataclass(frozen=True)
class UserCardData:
    telegram_user_id: int
    username: str | None
    email: str | None

    subscription_status: str | None
    paid_until: datetime | None
    auto_renew_enabled: bool | None

    last_payment_id: str | None
    last_payment_amount: str | None
    last_payment_currency: str | None
    last_payment_status: str | None
    last_payment_at: datetime | None

    source: str
    last_activity_at: datetime | None
    last_error_summary: str | None


class UserService:
    def __init__(self, *, db: Database, roles: RoleService) -> None:
        self._db = db
        self._roles = roles
        self._fmt = FormattingService()

    async def list_page(
        self,
        *,
        page: int,
        per_page: int = 15,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return (users_on_page, total_count) for pagination."""
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            pb = PaymentBotRepository(conn)
            total = await pb.count_users()
            rows = await pb.list_users_page(offset=page * per_page, limit=per_page)
            return [dict(r) for r in rows], total

    async def find_user(
        self,
        *,
        query: str,
    ) -> dict[str, Any] | None:
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        q = (query or "").strip()
        if not q:
            return None
        async with self._db.pool.acquire() as conn:
            pb = PaymentBotRepository(conn)
            if q.isdigit():
                u = await pb.find_user_by_telegram_id(int(q))
                return dict(u) if u else None
            if "@" in q and " " not in q and "." in q:
                u = await pb.find_user_by_email(q)
                return dict(u) if u else None
            u = await pb.find_user_by_username(q)
            return dict(u) if u else None

    async def build_user_card(self, *, telegram_user_id: int) -> tuple[UserCardData | None, str]:
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            pb = PaymentBotRepository(conn)
            ev = EventRepository(conn)
            ov = UserOverrideRepository(conn)

            user = await pb.find_user_by_telegram_id(telegram_user_id)
            if not user:
                return None, "Пользователь не найден в payment_bot."

            sub = await pb.get_subscription_by_user_id(int(user["id"]))
            last_payment = await pb.get_last_payment_for_user(int(user["id"]))

            override = await ov.get_override(telegram_user_id)
            if override:
                # Override affects only what admin-bot shows, not production truth.
                forced = str(override["mode"] or "")
                if forced == "no_sub":
                    sub_status = "inactive"
                    paid_until = None
                    auto_renew = False
                elif forced == "active":
                    sub_status = "active"
                    paid_until = datetime.now().astimezone()
                    auto_renew = True
                elif forced == "expired":
                    sub_status = "expired"
                    paid_until = datetime.now().astimezone()
                    auto_renew = False
                elif forced == "canceled":
                    sub_status = "canceled"
                    paid_until = datetime.now().astimezone()
                    auto_renew = False
                elif forced == "pending":
                    sub_status = "pending"
                    paid_until = None
                    auto_renew = False
                elif forced == "failed":
                    sub_status = "failed"
                    paid_until = None
                    auto_renew = False
                else:
                    sub_status = sub["status"] if sub else None
                    paid_until = sub["paid_until"] if sub else None
                    auto_renew = sub["auto_renew_enabled"] if sub else None
            else:
                sub_status = sub["status"] if sub else None
                paid_until = sub["paid_until"] if sub else None
                auto_renew = sub["auto_renew_enabled"] if sub else None

            # last activity/error from pb_events by telegram_user_id (payload_json)
            last_events = await ev.list_user_events(telegram_user_id=telegram_user_id, limit=1)
            last_activity_at = last_events[0]["created_at"] if last_events else None

            last_errors = await ev.list_user_events(telegram_user_id=telegram_user_id, limit=1, only_errors=True)
            last_error_summary = None
            if last_errors:
                payload = last_errors[0]["payload_json"] or {}
                if isinstance(payload, str):
                    last_error_summary = payload[:200]
                elif isinstance(payload, dict):
                    last_error_summary = str(payload.get("error_message") or payload.get("event_type") or "Ошибка")[:200]
                else:
                    last_error_summary = "Ошибка"

            card = UserCardData(
                telegram_user_id=int(user["telegram_user_id"]),
                username=(user["username"] or None),
                email=(user["email"] or None),
                subscription_status=sub_status,
                paid_until=paid_until,
                auto_renew_enabled=auto_renew,
                last_payment_id=last_payment["payment_id"] if last_payment else None,
                last_payment_amount=str(last_payment["amount"]) if last_payment else None,
                last_payment_currency=str(last_payment["currency"]) if last_payment else None,
                last_payment_status=str(last_payment["status"]) if last_payment else None,
                last_payment_at=last_payment["created_at"] if last_payment else None,
                source="payment_bot",
                last_activity_at=last_activity_at,
                last_error_summary=last_error_summary,
            )
            text = self._fmt.user_card(
                telegram_user_id=card.telegram_user_id,
                username=card.username,
                email=card.email,
                sub_status=card.subscription_status,
                paid_until=card.paid_until,
                auto_renew_enabled=card.auto_renew_enabled,
                last_payment_amount=card.last_payment_amount,
                last_payment_currency=card.last_payment_currency,
                last_payment_status=card.last_payment_status,
                last_payment_at=card.last_payment_at,
                source=card.source,
                last_activity_at=card.last_activity_at,
                last_error_summary=card.last_error_summary,
            )
            if override:
                text = text + "\n\n🧪 <b>Тест-режим:</b> включён (показываем состояние по override)"
            return card, text

