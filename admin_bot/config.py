from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from pathlib import Path


def _required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ValueError(f"Missing required env variable: {name}")
    return value


def _optional_int(name: str) -> int | None:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    return int(raw)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_telegram_id: int
    postgres_dsn: str

    bot_mode: str
    webhook_base_url: str | None
    telegram_webhook_path: str
    telegram_webhook_secret: str | None

    admin_chat_id: int | None
    admin_thread_id: int | None

    log_level: str
    timezone: str
    health_report_cron: str

    # System panel (Docker management)
    docker_project_name: str        # docker compose project name (container name prefix)
    docker_compose_dir: str | None  # path to docker-compose.yml directory (optional)

    # Broadcast (payment_bot token to send messages as payment_bot)
    payment_bot_token: str | None

    @property
    def telegram_webhook_url(self) -> str | None:
        if not self.webhook_base_url:
            return None
        return f"{self.webhook_base_url.rstrip('/')}{self.telegram_webhook_path}"


def load_settings() -> Settings:
    # Always load admin_bot/.env explicitly (don't depend on CWD).
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
    bot_mode = (os.getenv("BOT_MODE") or "polling").strip().lower()
    webhook_base = (os.getenv("WEBHOOK_BASE_URL") or "").strip() or None
    webhook_secret = (os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip() or None
    return Settings(
        bot_token=_required("BOT_TOKEN"),
        owner_telegram_id=int(_required("OWNER_TELEGRAM_ID")),
        postgres_dsn=_required("POSTGRES_DSN"),
        bot_mode=bot_mode,
        webhook_base_url=webhook_base,
        telegram_webhook_path=(os.getenv("TELEGRAM_WEBHOOK_PATH") or "/webhook/admin").strip(),
        telegram_webhook_secret=webhook_secret,
        admin_chat_id=_optional_int("ADMIN_CHAT_ID"),
        admin_thread_id=_optional_int("ADMIN_THREAD_ID"),
        log_level=(os.getenv("LOG_LEVEL") or "INFO").strip().upper(),
        timezone=(os.getenv("TIMEZONE") or "Europe/Moscow").strip(),
        health_report_cron=(os.getenv("HEALTH_REPORT_CRON") or "0 */12 * * *").strip(),
        docker_project_name=(os.getenv("DOCKER_PROJECT_NAME") or "actualppbotnooplata_stage").strip(),
        docker_compose_dir=(os.getenv("DOCKER_COMPOSE_DIR") or "").strip() or None,
        payment_bot_token=(os.getenv("PAYMENT_BOT_TOKEN") or "").strip() or None,
    )

