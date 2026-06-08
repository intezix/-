from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_bot.app_context import AppContext
from admin_bot.db.repositories import EventRepository
from admin_bot.keyboards.inline import InlineKeyboards


router = Router()
kb = InlineKeyboards()

def _short_error_row(r) -> str:
    created = r["created_at"].astimezone().strftime("%m-%d %H:%M")
    payload = r["payload_json"] or {}
    if isinstance(payload, dict):
        source = payload.get("source_bot") or "—"
        who = payload.get("telegram_user_id") or "—"
        msg = payload.get("error_message") or payload.get("event_type") or r["event_type"]
        if msg and len(str(msg)) > 120:
            msg = str(msg)[:120] + "…"
        return f"{created} — <b>{source}</b> — <code>{who}</code> — {msg} (id={r['id']})"
    return f"{created} — {r['event_type']} (id={r['id']})"


@router.message(Command("errors"))
async def cmd_errors(message: Message, ctx: AppContext) -> None:
    await ctx.roles.require_access(message.from_user.id)
    await _send_errors(message, ctx=ctx)

@router.callback_query(lambda c: c.data == "errors:list")
async def cb_errors_list(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    await _send_errors(callback, ctx=ctx)


async def _send_errors(target: Message | CallbackQuery, *, ctx: AppContext) -> None:
    if not ctx.db.pool:
        raise RuntimeError("DB not connected")
    async with ctx.db.pool.acquire() as conn:
        repo = EventRepository(conn)
        rows = await repo.list_recent_errors(limit=20)
    if not rows:
        text = "🚨 <b>Ошибки</b>\n\nКритичных ошибок не найдено."
        if isinstance(target, Message):
            await target.answer(text, reply_markup=kb.to_menu())
        else:
            await target.message.edit_text(text, reply_markup=kb.to_menu())
            await target.answer()
        return
    lines = ["🚨 <b>Ошибки</b>", "", "Последние события:"]
    for r in rows:
        lines.append(_short_error_row(r))
    # Inline buttons to open each error card
    btn_rows: list[list[InlineKeyboardButton]] = []
    for r in rows[:10]:
        btn_rows.append([InlineKeyboardButton(text=f"🧾 Ошибка #{r['id']}", callback_data=f"err:open:{r['id']}")])
    final_markup = InlineKeyboardMarkup(inline_keyboard=btn_rows + kb.to_menu().inline_keyboard)
    if isinstance(target, Message):
        await target.answer("\n".join(lines), reply_markup=final_markup)
    else:
        await target.message.edit_text("\n".join(lines), reply_markup=final_markup)
        await target.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("err:open:"))
async def cb_error_open(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    event_id = int((callback.data or "").split(":")[2])
    await _send_error_card(callback, ctx=ctx, event_id=event_id)


@router.message(Command("error"))
async def cmd_error(message: Message, ctx: AppContext) -> None:
    await ctx.roles.require_access(message.from_user.id)
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Использование: /error <event_id>", reply_markup=kb.to_menu())
        return
    event_id = int(parts[1].strip())
    await _send_error_card(message, ctx=ctx, event_id=event_id)


async def _send_error_card(target: Message | CallbackQuery, *, ctx: AppContext, event_id: int) -> None:
    if not ctx.db.pool:
        raise RuntimeError("DB not connected")
    async with ctx.db.pool.acquire() as conn:
        repo = EventRepository(conn)
        row = await repo.get_event(event_id)
    if not row:
        text = "Ошибка не найдена."
        if isinstance(target, Message):
            await target.answer(text, reply_markup=kb.to_menu())
        else:
            await target.message.edit_text(text, reply_markup=kb.to_menu())
            await target.answer()
        return
    payload = row["payload_json"] or {}
    if not isinstance(payload, dict):
        payload = {"error_message": str(payload)}
    payload = dict(payload)
    payload.setdefault("created_at", row["created_at"].astimezone().strftime("%Y-%m-%d %H:%M %Z"))
    payload.setdefault("event_type", row["event_type"])
    text = ctx.alerts._fmt.error_alert(payload)  # local formatting reuse
    keyboard = kb.error_actions(event_id=event_id, telegram_user_id=payload.get("telegram_user_id"))
    if isinstance(target, Message):
        await target.answer(text, reply_markup=keyboard)
    else:
        await target.message.edit_text(text, reply_markup=keyboard)
        await target.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("err:resolve:"))
async def resolve_error(callback: CallbackQuery, ctx: AppContext) -> None:
    await ctx.roles.require_access(callback.from_user.id)
    event_id = int((callback.data or "").split(":")[2])
    if not ctx.db.pool:
        raise RuntimeError("DB not connected")
    async with ctx.db.pool.acquire() as conn:
        repo = EventRepository(conn)
        await repo.mark_resolved(event_id, callback.from_user.id)
    await callback.answer("Помечено")
    await callback.message.edit_text("✅ Ошибка помечена как решённая.", reply_markup=kb.to_menu())


@router.callback_query(lambda c: c.data and c.data.startswith("err:logs:"))
async def logs_before_error(callback: CallbackQuery, ctx: AppContext) -> None:
    """Show 20 most recent events for a user — context around an error."""
    await ctx.roles.require_access(callback.from_user.id)
    parts = (callback.data or "").split(":")
    event_id = int(parts[2])
    tg_id = int(parts[3])
    await callback.answer()
    if not ctx.db.pool:
        raise RuntimeError("DB not connected")
    async with ctx.db.pool.acquire() as conn:
        repo = EventRepository(conn)
        rows = await repo.list_user_events(telegram_user_id=tg_id, limit=20)
    if not rows:
        await callback.message.edit_text(
            f"📄 <b>Логи до ошибки #{event_id}</b>\n\nСобытия не найдены.",
            reply_markup=kb.back_and_menu(f"err:open:{event_id}"),
        )
        return
    lines = [
        "📄 <b>Логи пользователя</b>",
        f"Пользователь: <code>{tg_id}</code>",
        f"Контекст ошибки <code>#{event_id}</code>",
        "",
    ]
    for r in rows:
        created = r["created_at"].astimezone().strftime("%H:%M")
        payload = r["payload_json"] or {}
        if isinstance(payload, dict):
            if payload.get("status") == "error":
                msg = payload.get("error_message") or "Ошибка"
                lines.append(f"{created} — <b>ERROR</b>: {msg}")
            elif payload.get("callback_data"):
                lines.append(f"{created} — Кнопка: <code>{payload['callback_data']}</code>")
            elif payload.get("action"):
                lines.append(f"{created} — {payload['action']}")
            elif payload.get("message_text"):
                t = str(payload["message_text"])
                lines.append(f"{created} — Сообщение: {t[:90]}{'…' if len(t) > 90 else ''}")
            else:
                lines.append(f"{created} — {r['event_type']}")
        else:
            lines.append(f"{created} — {r['event_type']}")
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=kb.back_and_menu(f"err:open:{event_id}"),
    )

