import sqlite3
from datetime import datetime
from typing import Any
from config import DB_PATH

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def run_migrations() -> None:
    with get_connection() as conn:
        conn.executescript('\n            CREATE TABLE IF NOT EXISTS subscriptions (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                telegram_user_id TEXT UNIQUE NOT NULL,\n                status TEXT NOT NULL,\n                yk_subscription_id TEXT,\n                yk_payment_method_id TEXT,\n                yk_customer_id TEXT,\n                active_until TEXT,\n                created_at TEXT,\n                updated_at TEXT\n            );\n\n            CREATE TABLE IF NOT EXISTS tickets (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                telegram_user_id TEXT,\n                topic TEXT,\n                message_text TEXT,\n                created_at TEXT\n            );\n\n            CREATE TABLE IF NOT EXISTS user_topics (\n                telegram_user_id TEXT UNIQUE NOT NULL,\n                topic_thread_id INTEGER NOT NULL,\n                created_at TEXT\n            );\n\n            CREATE INDEX IF NOT EXISTS idx_sub_telegram ON subscriptions(telegram_user_id);\n            CREATE INDEX IF NOT EXISTS idx_sub_status ON subscriptions(telegram_user_id, status);\n            CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(telegram_user_id);\n            CREATE INDEX IF NOT EXISTS idx_topics_thread ON user_topics(topic_thread_id);\n            ')

def get_active_subscription(telegram_user_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM subscriptions WHERE telegram_user_id = ? AND status = 'active' LIMIT 1", (str(telegram_user_id),)).fetchone()
    if row is None:
        return None
    return dict(row)

def update_subscription_canceled(telegram_user_id: str) -> None:
    now = datetime.utcnow().isoformat() + 'Z'
    with get_connection() as conn:
        conn.execute("UPDATE subscriptions SET status = 'canceled', updated_at = ? WHERE telegram_user_id = ?", (now, str(telegram_user_id)))

def insert_ticket(telegram_user_id: str, topic: str, message_text: str) -> int:
    now = datetime.utcnow().isoformat() + 'Z'
    with get_connection() as conn:
        cur = conn.execute('INSERT INTO tickets (telegram_user_id, topic, message_text, created_at) VALUES (?, ?, ?, ?)', (str(telegram_user_id), topic, message_text or '', now))
        return cur.lastrowid or 0

def get_user_topic(telegram_user_id: str) -> int | None:
    with get_connection() as conn:
        row = conn.execute('SELECT topic_thread_id FROM user_topics WHERE telegram_user_id = ? LIMIT 1', (str(telegram_user_id),)).fetchone()
    if not row:
        return None
    return int(row['topic_thread_id'])

def save_user_topic(telegram_user_id: str, topic_thread_id: int) -> None:
    now = datetime.utcnow().isoformat() + 'Z'
    with get_connection() as conn:
        conn.execute('\n            INSERT INTO user_topics (telegram_user_id, topic_thread_id, created_at)\n            VALUES (?, ?, ?)\n            ON CONFLICT(telegram_user_id) DO UPDATE SET topic_thread_id = excluded.topic_thread_id\n            ', (str(telegram_user_id), int(topic_thread_id), now))

def get_user_by_topic(topic_thread_id: int) -> str | None:
    with get_connection() as conn:
        row = conn.execute('SELECT telegram_user_id FROM user_topics WHERE topic_thread_id = ? LIMIT 1', (int(topic_thread_id),)).fetchone()
    if not row:
        return None
    return str(row['telegram_user_id'])