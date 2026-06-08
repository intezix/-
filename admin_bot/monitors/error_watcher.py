from __future__ import annotations

import logging

from aiogram import Bot

from admin_bot.app_context import AppContext
from admin_bot.db.repositories import AlertDedupRepository, EventRepository


logger = logging.getLogger(__name__)


def _fingerprint(payload: dict) -> str:
    error_code = str(payload.get("error_code") or "")
    msg = str(payload.get("error_message") or "")
    action = str(payload.get("action") or "")
    # short, stable key
    base = (error_code.strip() + "|" + msg.strip() + "|" + action.strip()).strip("|")
    return base[:200] if base else "unknown"


async def error_watcher_job(bot: Bot, ctx: AppContext) -> None:
    """
    Sends new critical errors to admins in DM.
    Deduplication is stored in pb_events.payload_json.admin_notified=true.
    """
    try:
        if not ctx.db.pool:
            return
        async with ctx.db.pool.acquire() as conn:
            repo = EventRepository(conn)
            dedup = AlertDedupRepository(conn)
            rows = await repo.list_unnotified_errors(limit=10)
            for r in rows:
                event_id = int(r["id"])
                payload = r["payload_json"] or {}
                if not isinstance(payload, dict):
                    payload = {"error_message": str(payload)}
                payload = dict(payload)
                payload.setdefault("event_type", r["event_type"])
                payload.setdefault("created_at", r["created_at"].astimezone().strftime("%Y-%m-%d %H:%M %Z"))
                tg_id = payload.get("telegram_user_id")
                if isinstance(tg_id, (int, str)) and str(tg_id).isdigit():
                    recent = await repo.list_user_events(telegram_user_id=int(tg_id), limit=10)
                    payload["last_actions"] = [_short_event(x) for x in reversed(recent)]
                fp = _fingerprint(payload)
                if not await dedup.should_send(fingerprint=fp, cooldown_seconds=300):
                    # Still mark as notified to avoid endless scanning of the same rows
                    await repo.mark_admin_notified(event_id)
                    continue
                await ctx.alerts.send_error_alert(bot=bot, event_id=event_id, payload=payload)
                await dedup.mark_sent(fingerprint=fp)
                await repo.mark_admin_notified(event_id)
    except Exception as e:
        logger.exception("Error watcher job failed: %s", e)


def _short_event(r) -> str:
    created = r["created_at"].astimezone().strftime("%H:%M")
    payload = r["payload_json"] or {}
    if isinstance(payload, dict):
        if payload.get("status") == "error":
            msg = payload.get("error_message") or "Ошибка"
            return f"{created} — ERROR: {msg}"
        cb = payload.get("callback_data")
        if cb:
            return f"{created} — нажал: {cb}"
        action = payload.get("action")
        if action:
            return f"{created} — {action}"
        text = payload.get("message_text")
        if text:
            s = str(text).replace("\n", " ")
            if len(s) > 80:
                s = s[:80] + "…"
            return f"{created} — ввёл: {s}"
    return f"{created} — {r['event_type']}"

