import sqlite3
from pathlib import Path
from typing import List, Set, Optional
from datetime import datetime

class FavouritesService:
    _instance: Optional['FavouritesService'] = None
    _db_path: Path = None

    def __new__(cls) -> 'FavouritesService':
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
        cursor.execute('\n            CREATE TABLE IF NOT EXISTS users (\n                user_id INTEGER PRIMARY KEY,\n                fav_hint_shown INTEGER DEFAULT 0\n            )\n        ')
        cursor.execute('\n            CREATE TABLE IF NOT EXISTS favourites (\n                user_id INTEGER NOT NULL,\n                recipe_id TEXT NOT NULL,\n                created_at TEXT NOT NULL,\n                PRIMARY KEY (user_id, recipe_id),\n                FOREIGN KEY (user_id) REFERENCES users(user_id)\n            )\n        ')
        cursor.execute('\n            CREATE INDEX IF NOT EXISTS idx_favourites_user_id \n            ON favourites(user_id)\n        ')
        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def is_hint_shown(self, user_id: int) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT fav_hint_shown FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        if result is None:
            return False
        return bool(result[0])

    def mark_hint_shown(self, user_id: int) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('\n            INSERT OR REPLACE INTO users (user_id, fav_hint_shown)\n            VALUES (?, 1)\n        ', (user_id,))
        conn.commit()
        conn.close()

    def add_favourite(self, user_id: int, recipe_id: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            created_at = datetime.now().isoformat()
            cursor.execute('\n                INSERT INTO favourites (user_id, recipe_id, created_at)\n                VALUES (?, ?, ?)\n            ', (user_id, recipe_id, created_at))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def remove_favourite(self, user_id: int, recipe_id: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('\n            DELETE FROM favourites\n            WHERE user_id = ? AND recipe_id = ?\n        ', (user_id, recipe_id))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def is_favourite(self, user_id: int, recipe_id: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('\n            SELECT 1 FROM favourites\n            WHERE user_id = ? AND recipe_id = ?\n            LIMIT 1\n        ', (user_id, recipe_id))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def get_favourite_recipe_ids(self, user_id: int) -> List[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('\n            SELECT recipe_id FROM favourites\n            WHERE user_id = ?\n            ORDER BY created_at DESC\n        ', (user_id,))
        results = cursor.fetchall()
        conn.close()
        return [row[0] for row in results]

    def get_favourite_count(self, user_id: int) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('\n            SELECT COUNT(*) FROM favourites\n            WHERE user_id = ?\n        ', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0