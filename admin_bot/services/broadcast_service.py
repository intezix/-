from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from admin_bot.db.database import Database
from admin_bot.db.repositories import PaymentBotRepository
from admin_bot.services.role_service import RoleService

logger = logging.getLogger(__name__)

# Telegram позволяет 30 сообщений/сек, ставим небольшой запас
_BATCH_PAUSE = 0.04   # ~25 msg/s
_STOP_ON_ERRORS = 50  # прерываем рассылку если слишком много ошибок


@dataclass
class BroadcastResult:
    total: int
    sent: int
    blocked: int   # TelegramForbiddenError — пользователь заблокировал бота
    errors: int
    stopped_early: bool = False


class BroadcastService:
    """Рассылка сообщений всем пользователям из pb_users через токен payment_bot."""

    def __init__(
        self,
        *,
        db: Database,
        roles: RoleService,
        payment_bot_token: str | None,
    ) -> None:
        self._db = db
        self._roles = roles
        self._token = payment_bot_token

    def is_configured(self) -> bool:
        return bool(self._token)

    async def send_to_all(
        self,
        *,
        actor_telegram_user_id: int,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
    ) -> BroadcastResult:
        """
        Отправляет text всем пользователям из pb_users.
        Использует payment_bot_token чтобы пользователи получили сообщение
        от знакомого им бота.
        """
        await self._roles.require_access(actor_telegram_user_id)

        if not self._token:
            raise RuntimeError("PAYMENT_BOT_TOKEN не настроен")
        if not self._db.pool:
            raise RuntimeError("DB not connected")

        # Получаем список получателей
        async with self._db.pool.acquire() as conn:
            repo = PaymentBotRepository(conn)
            user_ids = await repo.list_all_telegram_user_ids()

        total = len(user_ids)
        sent = blocked = errors = 0
        stopped_early = False

        bot = Bot(
            token=self._token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        try:
            for tg_id in user_ids:
                try:
                    await bot.send_message(
                        chat_id=tg_id,
                        text=text,
                        disable_web_page_preview=disable_web_page_preview,
                    )
                    sent += 1
                except TelegramForbiddenError:
                    # Пользователь заблокировал бота — нормальная ситуация
                    blocked += 1
                except TelegramBadRequest as e:
                    logger.warning("broadcast bad request to %s: %s", tg_id, e)
                    errors += 1
                except Exception as e:
                    logger.warning("broadcast error to %s: %s", tg_id, e)
                    errors += 1

                if errors >= _STOP_ON_ERRORS:
                    stopped_early = True
                    break

                await asyncio.sleep(_BATCH_PAUSE)
        finally:
            await bot.session.close()

        return BroadcastResult(
            total=total,
            sent=sent,
            blocked=blocked,
            errors=errors,
            stopped_early=stopped_early,
        )
