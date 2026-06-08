from __future__ import annotations

from datetime import UTC, datetime

from admin_bot.services.formatting_service import FormattingService
from pp_common.lifetime_access import lifetime_paid_until


def test_subscription_status_ru() -> None:
    fmt = FormattingService()
    assert fmt.subscription_status_ru("active") == "активна"
    assert fmt.subscription_status_ru("expired") == "истекла"
    assert fmt.subscription_status_ru(None) == "—"


def test_payment_status_ru() -> None:
    fmt = FormattingService()
    assert fmt.payment_status_ru("succeeded") == "успешно"
    assert fmt.payment_status_ru("pending") == "в обработке"


def test_user_card_renders() -> None:
    fmt = FormattingService()
    text = fmt.user_card(
        telegram_user_id=1,
        username="u",
        email="e@mail.ru",
        sub_status="active",
        paid_until=lifetime_paid_until(),
        auto_renew_enabled=False,
        last_payment_amount="590.00",
        last_payment_currency="RUB",
        last_payment_status="succeeded",
        last_payment_at=datetime.now(tz=UTC),
        source="payment_bot",
        last_activity_at=datetime.now(tz=UTC),
        last_error_summary=None,
    )
    assert "👤 Пользователь" in text
    assert "Статус: <b>активна</b>" in text
    assert "бессрочный" in text

