from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import asyncpg


logger = logging.getLogger(__name__)


_POOL: asyncpg.Pool | None = None
MAX_PAYLOAD_BYTES = 4096


def _now_iso() -> str:
    return datetime.now(tz=UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _truncate_str(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    s = str(value)
    if len(s) <= max_len:
        return s
    return s[: max(0, max_len - 12)] + "…(обрезано)"


def _shrink_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Keep payload small (2–5 KB) to protect DB growth and index performance.
    Priority: keep identifiers and summary; truncate verbose fields first.
    """
    # First-pass truncation of obvious heavy fields.
    if "message_text" in payload:
        payload["message_text"] = _truncate_str(payload.get("message_text"), 300)
    if "callback_data" in payload:
        payload["callback_data"] = _truncate_str(payload.get("callback_data"), 200)
    if "error_message" in payload:
        payload["error_message"] = _truncate_str(payload.get("error_message"), 400)
    if "traceback" in payload:
        payload["traceback"] = _truncate_str(payload.get("traceback"), 1200)

    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) <= MAX_PAYLOAD_BYTES:
        return payload

    # Second-pass: drop big nested blobs.
    for k in ("context", "raw", "raw_response", "debug", "meta"):
        if k in payload:
            payload.pop(k, None)
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(raw) <= MAX_PAYLOAD_BYTES:
                return payload

    # Final-pass: hard trim by shortening traceback further.
    if "traceback" in payload:
        payload["traceback"] = _truncate_str(str(payload.get("traceback") or ""), 600)
    return payload


async def _get_pool() -> asyncpg.Pool:
    global _POOL
    if _POOL:
        return _POOL
    dsn = (os.getenv("POSTGRES_DSN") or "").strip()
    if not dsn:
        raise RuntimeError("POSTGRES_DSN is required for events_writer")
    _POOL = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)
    return _POOL


async def log_event(
    *,
    source_bot: str,
    telegram_user_id: int | None,
    event_type: str,
    action: str | None,
    screen: str | None,
    status: str | None,
    payload_json: dict[str, Any] | None,
    error_message: str | None = None,
    traceback: str | None = None,
    error_code: str | None = None,
    username: str | None = None,
    callback_data: str | None = None,
    message_text: str | None = None,
    correlation_id: str | None = None,
    conn: asyncpg.Connection | None = None,
    user_id: int | None = None,
) -> str:
    """
    Unified events writer for entire PP BOT ecosystem.

    Writes into payment_bot PostgreSQL table `pb_events`:
      - `event_type` column keeps a compact code
      - `payload_json` stores normalized rich context

    Fail-safe: never raises to caller (logs warning and returns).
    """
    payload: dict[str, Any] = dict(payload_json or {})
    payload.setdefault("source_bot", source_bot)
    if telegram_user_id is not None:
        payload.setdefault("telegram_user_id", int(telegram_user_id))
    if username:
        payload.setdefault("username", username.lstrip("@"))
    if action:
        payload.setdefault("action", action)
    if screen:
        payload.setdefault("screen", screen)
    if callback_data:
        payload.setdefault("callback_data", callback_data)
        payload.setdefault("event_group", payload.get("event_group") or "buttons")
    if message_text:
        payload.setdefault("message_text", message_text)
    if status:
        payload.setdefault("status", status)
    if error_code:
        payload.setdefault("error_code", error_code)
    if error_message:
        payload.setdefault("error_message", error_message)
    if traceback:
        payload.setdefault("traceback", traceback)
    payload.setdefault("correlation_id", correlation_id or payload.get("correlation_id") or str(uuid.uuid4()))
    payload.setdefault("time", payload.get("time") or _now_iso())
    payload.setdefault("event_type", payload.get("event_type") or event_type)
    payload = _shrink_payload(payload)

    try:
        if conn is None:
            pool = await _get_pool()
            async with pool.acquire() as c:
                await c.execute(
                    """
                    INSERT INTO pb_events (user_id, event_type, payload_json)
                    VALUES ($1, $2, $3::jsonb)
                    """,
                    user_id,
                    event_type,
                    json.dumps(payload, ensure_ascii=False),
                )
        else:
            await conn.execute(
                """
                INSERT INTO pb_events (user_id, event_type, payload_json)
                VALUES ($1, $2, $3::jsonb)
                """,
                user_id,
                event_type,
                json.dumps(payload, ensure_ascii=False),
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("events_writer failed (source=%s type=%s tg=%s): %s", source_bot, event_type, telegram_user_id, e)
    return str(payload.get("correlation_id") or "")

