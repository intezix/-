from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    bot_username: str
    bot_mode: str
    webhook_base_url: str
    telegram_webhook_path: str
    telegram_webhook_secret: str
    yookassa_webhook_path: str
    yookassa_shop_id: str
    yookassa_secret_key: str
    postgres_dsn: str
    admin_email_chat_id: int
    admin_email_thread_id: int | None
    subscription_price_rub: Decimal
    list_price_rub: Decimal
    subscription_days: int
    rate_limit_seconds: int
    pending_payment_ttl_minutes: int
    log_level: str
    main_bot_url: str
    support_bot_url: str
    community_chat_url: str
    offer_telegraph_url: str
    admin_ids: set[int]
    owner_ids: set[int]
    support_ids: set[int]
    viewer_ids: set[int]

    @property
    def telegram_webhook_url(self) -> str:
        return f"{self.webhook_base_url}{self.telegram_webhook_path}"


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required env variable: {name}")
    return value


def _parse_int_set(raw: str) -> set[int]:
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    out: set[int] = set()
    for p in parts:
        try:
            out.add(int(p))
        except ValueError:
            continue
    return out


def load_settings() -> Settings:
    load_dotenv()
    thread_raw = (os.getenv("ADMIN_EMAIL_THREAD_ID", "") or "").strip()
    return Settings(
        bot_token=_required("BOT_TOKEN"),
        bot_username=os.getenv("BOT_USERNAME", "payment_bot"),
        bot_mode=os.getenv("BOT_MODE", "webhook").lower(),
        webhook_base_url=_required("WEBHOOK_BASE_URL").rstrip("/"),
        telegram_webhook_path=os.getenv("TELEGRAM_WEBHOOK_PATH", "/webhook/telegram"),
        telegram_webhook_secret=_required("TELEGRAM_WEBHOOK_SECRET"),
        yookassa_webhook_path=os.getenv("YOOKASSA_WEBHOOK_PATH", "/webhook/yookassa"),
        yookassa_shop_id=_required("YOOKASSA_SHOP_ID"),
        yookassa_secret_key=_required("YOOKASSA_SECRET_KEY"),
        postgres_dsn=_required("POSTGRES_DSN"),
        admin_email_chat_id=int(_required("ADMIN_EMAIL_CHAT_ID")),
        admin_email_thread_id=int(thread_raw) if thread_raw else None,
        subscription_price_rub=Decimal(os.getenv("SUBSCRIPTION_PRICE_RUB", "990.00")),
        list_price_rub=Decimal(os.getenv("LIST_PRICE_RUB", "1190.00")),
        subscription_days=int(os.getenv("SUBSCRIPTION_DAYS", "30")),
        rate_limit_seconds=int(os.getenv("RATE_LIMIT_SECONDS", "2")),
        pending_payment_ttl_minutes=int(os.getenv("PENDING_PAYMENT_TTL_MINUTES", "30")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        main_bot_url=(os.getenv("MAIN_BOT_URL") or "https://t.me/bykatti_ppbot").strip(),
        support_bot_url=(os.getenv("SUPPORT_BOT_URL") or "https://t.me/bykatti_supportppbot").strip(),
        community_chat_url=(os.getenv("COMMUNITY_CHAT_URL") or "https://t.me/+9JjKjD0lEpw0M2Q6").strip(),
        offer_telegraph_url=os.getenv(
            "OFFER_TELEGRAPH_URL",
            "https://telegra.ph/Polzovatelskoe-soglashenie-PP-BOT-13-05-26",
        ),
        admin_ids=_parse_int_set(os.getenv("ADMIN_IDS", "")),
        owner_ids=_parse_int_set(os.getenv("OWNER_IDS", "")),
        support_ids=_parse_int_set(os.getenv("SUPPORT_IDS", "")),
        viewer_ids=_parse_int_set(os.getenv("VIEWER_IDS", "")),
    )

