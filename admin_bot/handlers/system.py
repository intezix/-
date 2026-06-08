from __future__ import annotations

import html
import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from admin_bot.app_context import AppContext
from admin_bot.keyboards.inline import InlineKeyboards
from admin_bot.services.system_service import MANAGED_SERVICES


router = Router()
kb = InlineKeyboards()
logger = logging.getLogger(__name__)


async def _edit(callback: CallbackQuery, text: str, **kwargs) -> None:
    try:
        await callback.message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


def _overview_text(statuses: list[dict]) -> str:
    lines = ["🖥️ <b>Система — статус контейнеров</b>", ""]
    for s in statuses:
        lines.append(f"{s['icon']} {s['label']}: <code>{s['state']}</code>")
    return "\n".join(lines)


# ── Overview (refresh) ────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "sys:overview")
async def sys_overview(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    await _edit(callback, "🖥️ <b>Система</b>\n\nЗагрузка…")
    statuses = await ctx.system.get_status()
    await _edit(callback, _overview_text(statuses), reply_markup=kb.system_overview(statuses))
    await callback.answer()


# ── Bot detail card ───────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("sys:bot:"))
async def sys_bot_detail(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    service = (callback.data or "").split(":", 2)[2]
    if service not in MANAGED_SERVICES:
        await callback.answer("Неизвестный сервис", show_alert=True)
        return

    label = MANAGED_SERVICES[service]
    statuses = await ctx.system.get_status()
    info = next((s for s in statuses if s["service"] == service), None)
    icon = info["icon"] if info else "❓"
    state_txt = info["state"] if info else "неизвестно"

    text = "\n".join(
        [
            f"{icon} <b>{label}</b>",
            "",
            f"Контейнер: <code>{ctx.system._container_name(service)}</code>",
            f"Статус: <b>{state_txt}</b>",
        ]
    )
    await _edit(callback, text, reply_markup=kb.bot_detail(service))
    await callback.answer()


# ── Restart: confirm ─────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("sys:restart:"))
async def sys_restart_confirm(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    service = (callback.data or "").split(":", 2)[2]
    if service not in MANAGED_SERVICES:
        await callback.answer("Неизвестный сервис", show_alert=True)
        return
    label = MANAGED_SERVICES[service]
    text = "\n".join(
        [
            f"🔄 <b>Перезапустить {label}?</b>",
            "",
            f"Контейнер: <code>{ctx.system._container_name(service)}</code>",
            "",
            "⚠️ Бот будет недоступен несколько секунд.",
        ]
    )
    await _edit(callback, text, reply_markup=kb.restart_confirm(service))
    await callback.answer()


# ── Restart: execute ─────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("sys:do_restart:"))
async def sys_do_restart(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    service = (callback.data or "").split(":", 2)[2]
    if service not in MANAGED_SERVICES:
        await callback.answer("Неизвестный сервис", show_alert=True)
        return
    label = MANAGED_SERVICES[service]

    await _edit(callback, f"🔄 Перезапускаю <b>{label}</b>…")
    success, output = await ctx.system.restart(service)

    if success:
        result_text = f"✅ <b>{label}</b> перезапущен."
        logger.info("admin %s restarted %s", callback.from_user.id, service)
    else:
        result_text = f"❌ Ошибка при перезапуске <b>{label}</b>:\n<code>{output[:300]}</code>"
        logger.warning("restart %s failed: %s", service, output[:300])

    # После рестарта показываем обновлённый статус
    statuses = await ctx.system.get_status()
    full_text = result_text + "\n\n" + _overview_text(statuses)
    await _edit(callback, full_text, reply_markup=kb.system_overview(statuses))
    await callback.answer("Готово" if success else "Ошибка!", show_alert=not success)


# ── Logs ──────────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("sys:logs:"))
async def sys_logs(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    service = (callback.data or "").split(":", 2)[2]
    if service not in MANAGED_SERVICES:
        await callback.answer("Неизвестный сервис", show_alert=True)
        return
    label = MANAGED_SERVICES[service]

    await callback.answer("Загружаю логи…")
    raw = await ctx.system.get_logs(service, lines=50)

    # Telegram ограничивает сообщение 4096 символами
    header = f"📋 <b>Логи — {label}</b>\n\n<pre>"
    footer = "</pre>"
    max_log = 4096 - len(header) - len(footer) - 10
    if len(raw) > max_log:
        raw = "…(обрезано)\n" + raw[-max_log:]

    # IMPORTANT: docker logs may contain '<', '&', etc. Escape to keep HTML valid.
    safe_raw = html.escape(raw)
    text = header + safe_raw + footer
    # Отправляем новым сообщением (старое оставляем) — логи обычно длинные
    await callback.message.answer(text, reply_markup=kb.bot_detail(service))
