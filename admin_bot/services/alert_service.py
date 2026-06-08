from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from admin_bot.config import Settings
from admin_bot.db.database import Database
from admin_bot.db.repositories import AdminUserRepository
from admin_bot.keyboards.inline import InlineKeyboards
from admin_bot.services.formatting_service import FormattingService
from admin_bot.services.role_service import RoleService


logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self, *, db: Database, roles: RoleService, settings: Settings) -> None:
        self._db = db
        self._roles = roles
        self._settings = settings
        self._fmt = FormattingService()
        self._kb = InlineKeyboards()

    async def recipients_for(self, notify_kind: str) -> list[int]:
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            repo = AdminUserRepository(conn)
            rows = await repo.list_notifiable_admins(notify_kind=notify_kind)
        ids = [int(r["telegram_user_id"]) for r in rows]
        if self._settings.owner_telegram_id not in ids:
            ids.insert(0, self._settings.owner_telegram_id)
        # Deduplicate, preserve order
        seen = set()
        out: list[int] = []
        for x in ids:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    async def send_error_alert(
        self,
        *,
        bot: Bot,
        event_id: int,
        payload: dict[str, Any],
    ) -> None:
        text = self._fmt.error_alert(payload)
        keyboard = self._kb.error_actions(event_id=event_id, telegram_user_id=payload.get("telegram_user_id"))
        recipients = await self.recipients_for("errors")
        for chat_id in recipients:
            await self._safe_send(bot, chat_id=chat_id, text=text, reply_markup=keyboard)

        # Optional admin-chat mirror if configured
        if self._settings.admin_chat_id:
            await self._safe_send(
                bot,
                chat_id=self._settings.admin_chat_id,
                text=text,
                reply_markup=keyboard,
                message_thread_id=self._settings.admin_thread_id,
            )

    async def send_health_report(
        self,
        *,
        bot: Bot,
        text: str,
    ) -> None:
        recipients = await self.recipients_for("health")
        for chat_id in recipients:
            await self._safe_send(bot, chat_id=chat_id, text=text, reply_markup=self._kb.to_menu())

        if self._settings.admin_chat_id:
            await self._safe_send(
                bot,
                chat_id=self._settings.admin_chat_id,
                text=text,
                reply_markup=self._kb.to_menu(),
                message_thread_id=self._settings.admin_thread_id,
            )

    @staticmethod
    async def _safe_send(
        bot: Bot,
        *,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        message_thread_id: int | None = None,
    ) -> None:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                message_thread_id=message_thread_id,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.warning("Не удалось отправить уведомление (chat_id=%s): %s", chat_id, e)

