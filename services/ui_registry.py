import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UiMessageRow:
    user_id: int
    chat_id: int
    message_id: int
    kind: str
    is_persistent: bool
    created_at: int


class UiRegistry:
    """
    Persistent registry of "UI messages" per user.
    Used to reliably delete/update UI after inactivity resets.
    """

    def __init__(self) -> None:
        base_path = Path(__file__).resolve().parent.parent
        self._db_path = base_path / "data" / "ui_registry.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ui_messages(
                  user_id INTEGER NOT NULL,
                  chat_id INTEGER NOT NULL,
                  message_id INTEGER NOT NULL,
                  kind TEXT,
                  is_persistent INTEGER DEFAULT 0,
                  created_at INTEGER NOT NULL,
                  PRIMARY KEY(user_id, message_id)
                );

                CREATE INDEX IF NOT EXISTS idx_ui_messages_user ON ui_messages(user_id);
                CREATE INDEX IF NOT EXISTS idx_ui_messages_kind ON ui_messages(kind);
                CREATE INDEX IF NOT EXISTS idx_ui_messages_user_kind ON ui_messages(user_id, kind);
                """
            )

    def register_ui_message(
        self,
        user_id: int,
        chat_id: int,
        message_id: int,
        kind: str,
        is_persistent: bool = False,
    ) -> None:
        if message_id is None:
            return
        created_at = int(time.time())
        with self._lock, self._connect() as conn:
            # Keep only one persistent row per user (the "first welcome" message).
            if is_persistent:
                conn.execute(
                    """
                    UPDATE ui_messages
                    SET is_persistent = 0
                    WHERE user_id = ?
                      AND is_persistent = 1
                      AND message_id != ?
                    """,
                    (user_id, message_id),
                )

            conn.execute(
                """
                INSERT INTO ui_messages (user_id, chat_id, message_id, kind, is_persistent, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, message_id) DO UPDATE SET
                    chat_id = excluded.chat_id,
                    kind = excluded.kind,
                    is_persistent = excluded.is_persistent,
                    created_at = excluded.created_at
                """,
                (user_id, chat_id, message_id, kind, 1 if is_persistent else 0, created_at),
            )

        logger.info(
            "[UI_REGISTRY] register user=%s msg=%s kind=%s persistent=%s",
            user_id,
            message_id,
            kind,
            int(is_persistent),
        )

    def get_user_ui_messages(self, user_id: int) -> list[UiMessageRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, chat_id, message_id, kind, is_persistent, created_at
                FROM ui_messages
                WHERE user_id = ?
                ORDER BY created_at ASC
                """,
                (user_id,),
            ).fetchall()
        return [
            UiMessageRow(
                user_id=int(r["user_id"]),
                chat_id=int(r["chat_id"]),
                message_id=int(r["message_id"]),
                kind=str(r["kind"] or ""),
                is_persistent=bool(r["is_persistent"]),
                created_at=int(r["created_at"]),
            )
            for r in rows
        ]

    def _delete_from_db_only(self, user_id: int, message_id: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM ui_messages WHERE user_id = ? AND message_id = ?",
                (user_id, message_id),
            )

    def delete_ui_message(
        self,
        user_id: int,
        message_id: int,
        bot=None,
        chat_id: Optional[int] = None,
        kind: Optional[str] = None,
    ) -> None:
        """
        Idempotent delete:
        - tries Telegram delete
        - if Telegram doesn't allow, tries edit_reply_markup(reply_markup=None)
        - always removes record from DB
        """
        if message_id is None:
            return

        # Load row if we need chat_id for Telegram operations.
        row: Optional[sqlite3.Row] = None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT chat_id, kind
                FROM ui_messages
                WHERE user_id = ? AND message_id = ?
                """,
                (user_id, message_id),
            ).fetchone()

        effective_chat_id = int(chat_id) if chat_id is not None else (int(row["chat_id"]) if row else None)
        effective_kind = kind if kind is not None else (str(row["kind"]) if row else "")

        # Telegram delete attempts are best-effort; DB row removal is mandatory.
        if bot is not None and effective_chat_id is not None:
            try:
                logger.info(
                    "[UI_REGISTRY] clear ok user=%s msg=%s kind=%s",
                    user_id,
                    message_id,
                    effective_kind,
                )
                bot_loop = getattr(bot, "_loop", None)
                # We don't await here: this helper is used as sync wrapper from async context.
            except Exception:
                # just continue; actual deletion happens below
                pass

        if bot is not None and effective_chat_id is not None:
            try:
                import asyncio

                async def _try_delete() -> None:
                    try:
                        await bot.delete_message(chat_id=effective_chat_id, message_id=message_id)
                    except Exception:
                        # Fallback: remove inline keyboard/reply markup if possible.
                        try:
                            await bot.edit_message_reply_markup(
                                chat_id=effective_chat_id,
                                message_id=message_id,
                                reply_markup=None,
                            )
                        except Exception:
                            # Telegram might not allow any edits/deletes; still clean DB.
                            return

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # In async context we will call this from a sync function? Avoid deadlock.
                    # We'll schedule a task and return; DB cleanup happens immediately below.
                    import asyncio as _asyncio

                    _asyncio.create_task(_try_delete())
                else:
                    loop.run_until_complete(_try_delete())
            except Exception as e:
                logger.warning(
                    "[UI_REGISTRY] clear fail user=%s msg=%s kind=%s error=%s",
                    user_id,
                    message_id,
                    effective_kind,
                    e,
                )

        # Always remove DB record.
        self._delete_from_db_only(user_id, message_id)

    async def clear_user_ui_session(
        self,
        user_id: int,
        preserve_persistent: bool = True,
        preserve_message_ids: Optional[Iterable[int]] = None,
        bot=None,
    ) -> None:
        preserve_set = set(preserve_message_ids or [])
        logger.info("[UI_REGISTRY] clear start user=%s total=%s", user_id, len(self.get_user_ui_messages(user_id)))

        rows = self.get_user_ui_messages(user_id)
        to_delete = []
        for r in rows:
            if preserve_set and r.message_id in preserve_set:
                continue
            if preserve_persistent and r.is_persistent:
                continue
            to_delete.append(r)

        # Best-effort Telegram cleanup; DB cleanup must be guaranteed.
        for r in to_delete:
            if bot is not None:
                try:
                    try:
                        await bot.delete_message(chat_id=r.chat_id, message_id=r.message_id)
                        logger.info(
                            "[UI_REGISTRY] clear ok user=%s msg=%s kind=%s",
                            user_id,
                            r.message_id,
                            r.kind,
                        )
                    except Exception:
                        try:
                            await bot.edit_message_reply_markup(
                                chat_id=r.chat_id,
                                message_id=r.message_id,
                                reply_markup=None,
                            )
                            logger.info(
                                "[UI_REGISTRY] clear ok user=%s msg=%s kind=%s (edit markup)",
                                user_id,
                                r.message_id,
                                r.kind,
                            )
                        except Exception as e:
                            logger.warning(
                                "[UI_REGISTRY] clear fail user=%s msg=%s kind=%s error=%s",
                                user_id,
                                r.message_id,
                                r.kind,
                                e,
                            )
                except Exception as e:
                    logger.warning(
                        "[UI_REGISTRY] clear fail user=%s msg=%s kind=%s error=%s",
                        user_id,
                        r.message_id,
                        r.kind,
                        e,
                    )

            self._delete_from_db_only(r.user_id, r.message_id)

        logger.info("[UI_REGISTRY] clear ok user=%s", user_id)

    def _get_inactivity_prompt_rows(self, user_id: int) -> list[UiMessageRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, chat_id, message_id, kind, is_persistent, created_at
                FROM ui_messages
                WHERE user_id = ?
                  AND kind = 'inactivity_start'
                ORDER BY created_at ASC
                """,
                (user_id,),
            ).fetchall()
        return [
            UiMessageRow(
                user_id=int(r["user_id"]),
                chat_id=int(r["chat_id"]),
                message_id=int(r["message_id"]),
                kind=str(r["kind"] or ""),
                is_persistent=bool(r["is_persistent"]),
                created_at=int(r["created_at"]),
            )
            for r in rows
        ]

    async def remove_inactivity_prompt(self, user_id: int, bot=None) -> None:
        rows = self._get_inactivity_prompt_rows(user_id)
        if not rows:
            return
        for r in rows:
            if bot is not None:
                try:
                    try:
                        await bot.delete_message(chat_id=r.chat_id, message_id=r.message_id)
                    except Exception:
                        try:
                            await bot.edit_message_reply_markup(
                                chat_id=r.chat_id,
                                message_id=r.message_id,
                                reply_markup=None,
                            )
                        except Exception:
                            pass
                except Exception:
                    pass
            self._delete_from_db_only(r.user_id, r.message_id)
        logger.info("[UI_REGISTRY] inactivity prompt removed user=%s", user_id)


_REGISTRY: Optional[UiRegistry] = None
_REGISTRY_LOCK = threading.Lock()


def _get_registry() -> UiRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        with _REGISTRY_LOCK:
            if _REGISTRY is None:
                _REGISTRY = UiRegistry()
    return _REGISTRY


# Required helper-function API (thin wrappers around UiRegistry).


def register_ui_message(
    user_id: int,
    chat_id: int,
    message_id: int,
    kind: str,
    is_persistent: bool = False,
) -> None:
    _get_registry().register_ui_message(
        user_id=user_id,
        chat_id=chat_id,
        message_id=message_id,
        kind=kind,
        is_persistent=is_persistent,
    )


def get_user_ui_messages(user_id: int) -> list[UiMessageRow]:
    return _get_registry().get_user_ui_messages(user_id)


def delete_ui_message(
    user_id: int,
    message_id: int,
    bot=None,
    chat_id: Optional[int] = None,
    kind: Optional[str] = None,
) -> None:
    _get_registry().delete_ui_message(
        user_id=user_id,
        message_id=message_id,
        bot=bot,
        chat_id=chat_id,
        kind=kind,
    )


async def clear_user_ui_session(
    user_id: int,
    preserve_persistent: bool = True,
    preserve_message_ids: Optional[Iterable[int]] = None,
    bot=None,
) -> None:
    await _get_registry().clear_user_ui_session(
        user_id=user_id,
        preserve_persistent=preserve_persistent,
        preserve_message_ids=preserve_message_ids,
        bot=bot,
    )


async def remove_inactivity_prompt(user_id: int, bot=None) -> None:
    await _get_registry().remove_inactivity_prompt(user_id=user_id, bot=bot)


