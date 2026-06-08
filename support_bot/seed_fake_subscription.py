import sqlite3
from datetime import datetime

def main() -> None:
    path = 'support_bot.db'
    conn = sqlite3.connect(path)
    now = datetime.utcnow().isoformat() + 'Z'
    active_until = '2030-01-01T00:00:00Z'
    telegram_user_id = '613861214'
    cur = conn.execute('SELECT id FROM subscriptions WHERE telegram_user_id = ? LIMIT 1', (telegram_user_id,))
    row = cur.fetchone()
    sub_id = row[0] if row else None
    if sub_id is None:
        conn.execute("\n            INSERT INTO subscriptions\n            (telegram_user_id, status, yk_subscription_id, yk_payment_method_id, yk_customer_id, active_until, created_at, updated_at)\n            VALUES (?, 'active', NULL, NULL, NULL, ?, ?, ?)\n            ", (telegram_user_id, active_until, now, now))
    else:
        conn.execute("\n            UPDATE subscriptions\n            SET status = 'active',\n                active_until = ?,\n                updated_at = ?\n            WHERE id = ?\n            ", (active_until, now, sub_id))
    conn.commit()
    conn.close()
    print('Fake active subscription seeded for user', telegram_user_id)
if __name__ == '__main__':
    main()