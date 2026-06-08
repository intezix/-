from __future__ import annotations

import json
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from admin_bot.app_context import AppContext
from admin_bot.db.repositories import EventRepository
from admin_bot.keyboards.inline import InlineKeyboards


router = Router()
kb = InlineKeyboards()

def _fmt_event_row(r) -> str:
    created = r["created_at"].astimezone().strftime("%H:%M")
    payload = r["payload_json"] or {}
    if isinstance(payload, dict):
        status = payload.get("status")
        event_type = payload.get("event_type") or r["event_type"]
        action = payload.get("action")
        text = payload.get("message_text")
        cb = payload.get("callback_data")
        if status == "error":
            msg = payload.get("error_message") or "Ошибка"
            return f"{created} — <b>ERROR</b>: {msg}"
        if cb:
            return f"{created} — Нажатие кнопки: <code>{cb}</code>"
        if action:
            return f"{created} — {action}"
        if text:
            t = str(text)
            if len(t) > 90:
                t = t[:90] + "…"
            return f"{created} — Сообщение: {t}"
        return f"{created} — {event_type}"
    return f"{created} — {r['event_type']}"


@router.message(Command("logs"))
async def cmd_logs(message: Message, ctx: AppContext) -> None:
    await ctx.roles.require_access(message.from_user.id)
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Использование: /logs <telegram_user_id>", reply_markup=kb.to_menu())
        return
    tg_id = int(parts[1].strip())
    await _send_logs(message, ctx=ctx, telegram_user_id=tg_id, limit=20)


@router.callback_query(lambda c: c.data and c.data.startswith("user:logs:"))
async def user_logs(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    tg_id = int((callback.data or "").split(":")[2])
    await _send_logs(callback, ctx=ctx, telegram_user_id=tg_id, limit=20)


async def _send_logs(
    target: Message | CallbackQuery,
    *,
    ctx: AppContext,
    telegram_user_id: int,
    limit: int,
    **filters: Any,
) -> None:
    if not ctx.db.pool:
        raise RuntimeError("DB not connected")
    async with ctx.db.pool.acquire() as conn:
        repo = EventRepository(conn)
        rows = await repo.list_user_events(telegram_user_id=telegram_user_id, limit=limit, **filters)
    if not rows:
        text = "📄 <b>Логи пользователя</b>\n\nСобытия не найдены."
        if isinstance(target, Message):
            await target.answer(text, reply_markup=kb.back_and_menu(f"user:open:{telegram_user_id}"))
        else:
            await target.message.edit_text(text, reply_markup=kb.back_and_menu(f"user:open:{telegram_user_id}"))
            await target.answer()
        return
    lines = ["📄 <b>Логи пользователя</b>", f"Пользователь: <code>{telegram_user_id}</code>", ""]
    for r in rows:
        lines.append(_fmt_event_row(r))
    if isinstance(target, Message):
        await target.answer("\n".join(lines), reply_markup=kb.logs_filters(telegram_user_id))
    else:
        await target.message.edit_text("\n".join(lines), reply_markup=kb.logs_filters(telegram_user_id))
        await target.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("log:"))
async def logs_filter(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    parts = (callback.data or "").split(":")
    kind = parts[1]
    tg_id = int(parts[2])
    if kind == "errors":
        await _send_logs(callback, ctx=ctx, telegram_user_id=tg_id, limit=20, only_errors=True)
        return
    if kind == "payments":
        await _send_logs(callback, ctx=ctx, telegram_user_id=tg_id, limit=20, only_payments=True)
        return
    if kind == "buttons":
        await _send_logs(callback, ctx=ctx, telegram_user_id=tg_id, limit=20, only_buttons=True)
        return
    if kind == "more":
        await _send_logs(callback, ctx=ctx, telegram_user_id=tg_id, limit=50)
        return
    await callback.answer()

