from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot

from payment_bot.config import Settings
from payment_bot.db.database import Database
from payment_bot.services.rate_limit_service import CallbackDebounceService
from payment_bot.services.yookassa_service import YooKassaService


@dataclass
class AppContext:
    settings: Settings
    db: Database
    bot: Bot
    yookassa: YooKassaService
    debounce: CallbackDebounceService

