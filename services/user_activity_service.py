import sqlite3
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime, timezone

class UserActivityService:
    _instance: Optional['UserActivityService'] = None
    _db_path: Path = None

    def __new__(cls) -> 'UserActivityService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_db()
        return cls._instance

    def _init_db(self) -> None:
        base_path = Path(__file__).parent.parent
        self._db_path = base_path / 'data' / 'favourites.db'
        self._db_path.parent.mkdir(exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute('\n            CREATE TABLE IF NOT EXISTS user_activity (\n                user_id INTEGER PRIMARY KEY,\n                last_action_at INTEGER NOT NULL,\n                reminder_message_id INTEGER,\n                reminder_sent_at INTEGER\n            )\n            ')
        cursor.execute('\n            CREATE INDEX IF NOT EXISTS idx_user_activity_last_action_at\n            ON user_activity(last_action_at)\n            ')
        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    @staticmethod
    def _now_ts() -> int:
        return int(datetime.now(tz=timezone.utc).timestamp())

    def update_activity(self, user_id: int) -> None:
        ts = self._now_ts()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('\n            INSERT INTO user_activity (user_id, last_action_at, reminder_message_id, reminder_sent_at)\n            VALUES (?, ?, NULL, NULL)\n            ON CONFLICT(user_id) DO UPDATE SET\n                last_action_at = excluded.last_action_at\n            ', (user_id, ts))
        conn.commit()
        conn.close()

    def set_reminder(self, user_id: int, message_id: int) -> None:
        ts = self._now_ts()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('\n            INSERT INTO user_activity (user_id, last_action_at, reminder_message_id, reminder_sent_at)\n            VALUES (?, ?, ?, ?)\n            ON CONFLICT(user_id) DO UPDATE SET\n                reminder_message_id = excluded.reminder_message_id,\n                reminder_sent_at = excluded.reminder_sent_at\n            ', (user_id, ts, message_id, ts))
        conn.commit()
        conn.close()

    def set_soft_keyboard(self, user_id: int, message_id: int) -> None:
        """
        Сохраняем сообщение с клавиатурой «НАЧАТЬ» без отметки reminder_sent_at.
        Используется для «тихого» появления кнопки без текстового напоминания.
        """
        ts = self._now_ts()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '\n            INSERT INTO user_activity (user_id, last_action_at, reminder_message_id, reminder_sent_at)\n'
            '            VALUES (?, ?, ?, NULL)\n'
            '            ON CONFLICT(user_id) DO UPDATE SET\n'
            '                reminder_message_id = excluded.reminder_message_id,\n'
            '                reminder_sent_at = excluded.reminder_sent_at\n'
            '            ',
            (user_id, ts, message_id),
        )
        conn.commit()
        conn.close()

    def get_reminder_message_id(self, user_id: int) -> Optional[int]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('\n            SELECT reminder_message_id\n            FROM user_activity\n            WHERE user_id = ?\n            ', (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return row[0]

    def clear_reminder(self, user_id: int) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('\n            UPDATE user_activity\n            SET reminder_message_id = NULL,\n                reminder_sent_at = NULL\n            WHERE user_id = ?\n            ', (user_id,))
        conn.commit()
        conn.close()

    def get_users_for_inactivity_reminder(self, inactivity_seconds: int) -> List[Tuple[int, int]]:
        now_ts = self._now_ts()
        threshold = now_ts - inactivity_seconds
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('\n            SELECT user_id, last_action_at\n            FROM user_activity\n            WHERE last_action_at <= ?\n              AND (reminder_sent_at IS NULL)\n            ', (threshold,))
        rows = cursor.fetchall()
        conn.close()
        return [(row[0], row[1]) for row in rows]

    def get_users_for_soft_keyboard(self, inactivity_seconds: int) -> List[Tuple[int, int]]:
        """
        Пользователи, которым нужно «тихо» показать кнопку НАЧАТЬ (без текста).
        Берём только тех, у кого ещё нет активного напоминания/клавиатуры.
        """
        now_ts = self._now_ts()
        threshold = now_ts - inactivity_seconds
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '\n            SELECT user_id, last_action_at\n'
            '            FROM user_activity\n'
            '            WHERE last_action_at <= ?\n'
            '              AND reminder_message_id IS NULL\n'
            '            ',
            (threshold,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [(row[0], row[1]) for row in rows]

    def get_all_user_ids(self) -> List[int]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM user_activity")
        rows = cursor.fetchall()
        conn.close()
        return [int(r[0]) for r in rows]