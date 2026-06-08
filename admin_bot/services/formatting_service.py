from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pp_common.lifetime_access import is_lifetime_paid_until


class FormattingService:
    @staticmethod
    def _fmt_dt(dt: datetime | None) -> str:
        if not dt:
            return "—"
        # Telegram-friendly compact
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _fmt_bool(v: bool | None, *, yes: str, no: str) -> str:
        if v is None:
            return "—"
        return yes if v else no

    @staticmethod
    def subscription_status_ru(status: str | None) -> str:
        mapping = {
            "active": "активна",
            "inactive": "неактивна",
            "expired": "истекла",
            "canceled": "отменена",
            "pending": "в обработке",
            "failed": "ошибка",
            "past_due": "просрочена",
            None: "—",
            "": "—",
        }
        return mapping.get((status or "").lower(), status or "—")

    @staticmethod
    def payment_status_ru(status: str | None) -> str:
        mapping = {
            "succeeded": "успешно",
            "pending": "в обработке",
            "canceled": "отменён",
            "failed": "ошибка",
            "refunded": "возврат",
            None: "—",
            "": "—",
        }
        return mapping.get((status or "").lower(), status or "—")

    def user_card(
        self,
        *,
        telegram_user_id: int,
        username: str | None,
        email: str | None,
        sub_status: str | None,
        paid_until: datetime | None,
        auto_renew_enabled: bool | None,
        last_payment_amount: str | None,
        last_payment_currency: str | None,
        last_payment_status: str | None,
        last_payment_at: datetime | None,
        source: str,
        last_activity_at: datetime | None,
        last_error_summary: str | None,
    ) -> str:
        title = "👤 Пользователь"
        if sub_status == "active" and is_lifetime_paid_until(paid_until):
            access_line = "├ Доступ: <b>бессрочный</b>"
        elif paid_until:
            access_line = f"├ Оплачено до: <b>{self._fmt_dt(paid_until)}</b>"
        else:
            access_line = "├ Доступ: —"
        lines = [
            title,
            f"├ ID: <code>{telegram_user_id}</code>",
            f"├ Username: {('@' + username) if username else '—'}",
            f"├ Email: {email or '—'}",
            f"├ Статус: <b>{self.subscription_status_ru(sub_status)}</b>",
            access_line,
        ]
        if last_payment_amount and last_payment_currency:
            lines.append(
                f"├ Последний платёж: <b>{last_payment_amount} {last_payment_currency}</b>, "
                f"{self._fmt_dt(last_payment_at)}, {self.payment_status_ru(last_payment_status)}"
            )
        else:
            lines.append("├ Последний платёж: —")
        lines += [
            f"├ Источник: {source}",
            f"├ Последняя активность: {self._fmt_dt(last_activity_at)}",
            f"└ Последняя ошибка: {last_error_summary or '—'}",
        ]
        return "\n".join(lines)

    def payment_card(
        self,
        *,
        payment_id: str,
        telegram_user_id: int,
        email: str | None,
        amount: str,
        currency: str,
        status: str,
        is_recurring: bool,
        payment_method_saved: bool | None,
        admin_notified_at: datetime | None,
        created_at: datetime | None,
    ) -> str:
        t = "💳 Платёж"
        return "\n".join(
            [
                t,
                f"├ Payment ID: <code>{payment_id}</code>",
                f"├ User ID: <code>{telegram_user_id}</code>",
                f"├ Email: {email or '—'}",
                f"├ Сумма: <b>{amount} {currency}</b>",
                f"├ Статус: <b>{self.payment_status_ru(status)}</b>",
                f"├ Тип: {'устаревшее автосписание' if is_recurring else 'разовая оплата (бессрочный доступ)'}",
                f"├ Payment method saved: {self._fmt_bool(payment_method_saved, yes='да', no='нет')}",
                f"├ Admin notification: {'отправлено' if admin_notified_at else 'не отправлено'}",
                f"└ Дата: {self._fmt_dt(created_at)}",
            ]
        )

    def error_alert(self, payload: dict[str, Any]) -> str:
        source = payload.get("source_bot") or "—"
        event_type = payload.get("event_type") or payload.get("event") or "—"
        telegram_user_id = payload.get("telegram_user_id")
        username = payload.get("username")
        screen = payload.get("screen") or "—"
        action = payload.get("action") or "—"
        created_at = payload.get("created_at") or payload.get("time") or "—"

        error_message = payload.get("error_message") or "—"
        error_code = payload.get("error_code")
        traceback = payload.get("traceback") or ""
        context = payload.get("context") or {}
        last_actions = payload.get("last_actions") or []

        header = "🚨 <b>System Error</b>"
        who = "—"
        if telegram_user_id:
            who = f"<code>{telegram_user_id}</code>{(' / @' + username) if username else ''}"

        parts = [
            header,
            "",
            f"Источник: <b>{source}</b>",
            f"Событие: <b>{event_type}</b>",
            f"Пользователь: {who}",
            f"Экран: <code>{screen}</code>",
            f"Действие: <code>{action}</code>",
            f"Время: <code>{created_at}</code>",
            "",
            "<b>Ошибка:</b>",
            f"{(error_code + ': ') if error_code else ''}{error_message}",
        ]

        if context:
            ctx_text = json.dumps(context, ensure_ascii=False, indent=2)
            if len(ctx_text) > 3500:
                ctx_text = ctx_text[:3500] + "\n... (обрезано)"
            parts += ["", "<b>Контекст:</b>", f"<code>{ctx_text}</code>"]

        if traceback:
            tb = traceback.strip()
            if len(tb) > 3000:
                tb = tb[:3000] + "\n... (обрезано)"
            parts += ["", "<b>Trace:</b>", f"<pre>{tb}</pre>"]

        if last_actions:
            # last_actions is list[str]
            lines = []
            for x in list(last_actions)[:10]:
                s = str(x)
                if len(s) > 140:
                    s = s[:140] + "…"
                lines.append(s)
            parts += ["", "<b>Последние действия:</b>", "\n".join(lines)]

        return "\n".join(parts)

