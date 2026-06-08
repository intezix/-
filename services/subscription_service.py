import sqlite3
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import uuid
import re
from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, SUBSCRIPTION_PRICE_RUB, SUBSCRIPTION_PERIOD_DAYS


logger = logging.getLogger(__name__)


@dataclass
class Subscription:
    id: int
    user_id: int
    status: str
    paid_until: Optional[int]
    payment_method_id: Optional[str]
    canceled_at: Optional[int]


class SubscriptionService:
    _instance: Optional["SubscriptionService"] = None
    _db_path: Path = None

    def __new__(cls) -> "SubscriptionService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_db()
            cls._instance._init_yookassa()
        return cls._instance

    def _init_db(self) -> None:
        base_path = Path(__file__).parent.parent
        self._db_path = base_path / "data" / "favourites.db"
        self._db_path.parent.mkdir(exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_emails (
                user_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                paid_until INTEGER,
                payment_method_id TEXT,
                canceled_at INTEGER,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subscription_id INTEGER,
                payment_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL,
                is_recurrent INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _now_ts(self) -> int:
        return int(datetime.now(tz=timezone.utc).timestamp())

    def _init_yookassa(self) -> None:
        if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
            logger.warning("YooKassa credentials are not configured")
            return
        try:
            from yookassa import Configuration

            Configuration.configure(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
        except Exception as e:
            logger.exception("Failed to configure YooKassa: %s", e)

    def is_email_valid(self, email: str) -> bool:
        pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        return re.match(pattern, email) is not None

    def get_email(self, user_id: int) -> Optional[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT email FROM user_emails WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return row[0]

    def set_email(self, user_id: int, email: str) -> None:
        ts = self._now_ts()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_emails (user_id, email, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                email = excluded.email,
                updated_at = excluded.updated_at
            """,
            (user_id, email, ts, ts),
        )
        conn.commit()
        conn.close()

    def get_latest_subscription(self, user_id: int) -> Optional[Subscription]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, status, paid_until, payment_method_id, canceled_at
            FROM subscriptions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return Subscription(
            id=row[0],
            user_id=row[1],
            status=row[2],
            paid_until=row[3],
            payment_method_id=row[4],
            canceled_at=row[5],
        )

    def has_active_subscription(self, user_id: int) -> bool:
        sub = self.get_latest_subscription(user_id)
        if sub is None:
            return False
        if sub.status != "active":
            return False
        if sub.paid_until is None:
            return False
        return sub.paid_until > self._now_ts()

    def _ensure_subscription_for_user(self, user_id: int) -> int:
        sub = self.get_latest_subscription(user_id)
        ts = self._now_ts()
        conn = self._get_connection()
        cursor = conn.cursor()
        if sub is None:
            cursor.execute(
                """
                INSERT INTO subscriptions (user_id, status, paid_until, payment_method_id, canceled_at, created_at, updated_at)
                VALUES (?, ?, NULL, NULL, NULL, ?, ?)
                """,
                (user_id, "pending", ts, ts),
            )
            sub_id = cursor.lastrowid
        else:
            sub_id = sub.id
            cursor.execute(
                """
                UPDATE subscriptions
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                ("pending", ts, sub_id),
            )
        conn.commit()
        conn.close()
        return sub_id

    def create_payment(self, user_id: int, email: str) -> Tuple[str, str]:
        if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
            raise RuntimeError("YooKassa credentials are not configured")
        from yookassa import Payment

        sub_id = self._ensure_subscription_for_user(user_id)
        amount_value = f"{SUBSCRIPTION_PRICE_RUB:.2f}"
        idempotence_key = str(uuid.uuid4())
        description = "Подписка PP BOT 30 дней"
        payload = {
            "amount": {
                "value": amount_value,
                "currency": "RUB",
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/PP_BOT",
            },
            "capture": True,
            "save_payment_method": True,
            "description": description,
            "metadata": {
                "user_id": str(user_id),
                "subscription_id": str(sub_id),
            },
            "receipt": {
                "customer": {
                    "email": email,
                },
                "items": [
                    {
                        "description": description,
                        "quantity": "1.00",
                        "amount": {
                            "value": amount_value,
                            "currency": "RUB",
                        },
                        "vat_code": 1,
                        "payment_mode": "full_payment",
                        "payment_subject": "service",
                    }
                ],
            },
        }
        logger.info("Creating YooKassa payment for user %s, subscription %s", user_id, sub_id)
        payment = Payment.create(payload, idempotence_key)
        payment_id = str(payment.id)
        confirmation_url = str(payment.confirmation.confirmation_url)
        status = str(payment.status)
        ts = self._now_ts()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO payments (user_id, subscription_id, payment_id, amount, status, is_recurrent, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, sub_id, payment_id, SUBSCRIPTION_PRICE_RUB, status, 0, ts, ts),
        )
        conn.commit()
        conn.close()
        logger.info("Payment created id=%s status=%s", payment_id, status)
        return payment_id, confirmation_url

    def get_last_payment_id(self, user_id: int) -> Optional[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT payment_id
            FROM payments
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return row[0]

    def check_payment_and_update(self, payment_id: str) -> str:
        if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
            raise RuntimeError("YooKassa credentials are not configured")
        from yookassa import Payment

        logger.info("Checking YooKassa payment %s", payment_id)
        payment = Payment.find_one(payment_id)
        status = str(payment.status)
        payment_method_id = None
        try:
            payment_method_id = str(payment.payment_method.id)
        except Exception:
            payment_method_id = None
        ts = self._now_ts()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, subscription_id
            FROM payments
            WHERE payment_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (payment_id,),
        )
        row = cursor.fetchone()
        user_id = None
        sub_id = None
        if row is not None:
            user_id = row[0]
            sub_id = row[1]
        cursor.execute(
            """
            UPDATE payments
            SET status = ?, updated_at = ?
            WHERE payment_id = ?
            """,
            (status, ts, payment_id),
        )
        if status == "succeeded":
            paid_until = ts + SUBSCRIPTION_PERIOD_DAYS * 24 * 60 * 60
            if sub_id is None and user_id is not None:
                cursor.execute(
                    """
                    SELECT id
                    FROM subscriptions
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (user_id,),
                )
                sub_row = cursor.fetchone()
                if sub_row is not None:
                    sub_id = sub_row[0]
            if sub_id is not None:
                cursor.execute(
                    """
                    UPDATE subscriptions
                    SET status = ?, paid_until = ?, payment_method_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    ("active", paid_until, payment_method_id, ts, sub_id),
                )
            elif user_id is not None:
                cursor.execute(
                    """
                    INSERT INTO subscriptions (user_id, status, paid_until, payment_method_id, canceled_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, NULL, ?, ?)
                    """,
                    (user_id, "active", paid_until, payment_method_id, ts, ts),
                )
            logger.info("Payment %s succeeded, subscription activated until %s", payment_id, paid_until)
        elif status == "canceled":
            if sub_id is not None:
                cursor.execute(
                    """
                    UPDATE subscriptions
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    ("canceled", ts, sub_id),
                )
            logger.info("Payment %s canceled", payment_id)
        else:
            logger.info("Payment %s status=%s", payment_id, status)
        conn.commit()
        conn.close()
        return status

    def get_due_subscriptions(self) -> List[Subscription]:
        now_ts = self._now_ts()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, status, paid_until, payment_method_id, canceled_at
            FROM subscriptions
            WHERE status = 'active'
              AND paid_until IS NOT NULL
              AND paid_until <= ?
              AND (canceled_at IS NULL)
            """,
            (now_ts,),
        )
        rows = cursor.fetchall()
        conn.close()
        result: List[Subscription] = []
        for row in rows:
            result.append(
                Subscription(
                    id=row[0],
                    user_id=row[1],
                    status=row[2],
                    paid_until=row[3],
                    payment_method_id=row[4],
                    canceled_at=row[5],
                )
            )
        return result

    def run_billing_once(self) -> None:
        if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
            logger.warning("YooKassa credentials are not configured, billing skipped")
            return
        from yookassa import Payment

        subs = self.get_due_subscriptions()
        if not subs:
            logger.info("No subscriptions to bill")
            return
        logger.info("Running billing for %s subscriptions", len(subs))
        for sub in subs:
            if not sub.payment_method_id:
                logger.warning("Subscription %s has no payment_method_id", sub.id)
                continue
            amount_value = f"{SUBSCRIPTION_PRICE_RUB:.2f}"
            idempotence_key = str(uuid.uuid4())
            description = "Продление подписки PP BOT 30 дней"
            payload = {
                "amount": {
                    "value": amount_value,
                    "currency": "RUB",
                },
                "payment_method_id": sub.payment_method_id,
                "capture": True,
                "description": description,
                "metadata": {
                    "user_id": str(sub.user_id),
                    "subscription_id": str(sub.id),
                    "recurrent": "1",
                },
            }
            try:
                logger.info("Creating recurrent payment for subscription %s user %s", sub.id, sub.user_id)
                payment = Payment.create(payload, idempotence_key)
                payment_id = str(payment.id)
                status = str(payment.status)
                ts = self._now_ts()
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO payments (user_id, subscription_id, payment_id, amount, status, is_recurrent, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (sub.user_id, sub.id, payment_id, SUBSCRIPTION_PRICE_RUB, status, 1, ts, ts),
                )
                if status == "succeeded":
                    new_paid_until = ts + SUBSCRIPTION_PERIOD_DAYS * 24 * 60 * 60
                    cursor.execute(
                        """
                        UPDATE subscriptions
                        SET paid_until = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (new_paid_until, ts, sub.id),
                    )
                    logger.info("Recurrent payment %s succeeded, subscription %s extended to %s", payment_id, sub.id, new_paid_until)
                else:
                    cursor.execute(
                        """
                        UPDATE subscriptions
                        SET status = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        ("past_due", ts, sub.id),
                    )
                    logger.warning("Recurrent payment %s failed with status=%s, subscription %s set to past_due", payment_id, status, sub.id)
                conn.commit()
                conn.close()
            except Exception as e:
                logger.exception("Error while processing recurrent payment for subscription %s: %s", sub.id, e)

    def cancel_subscription(self, user_id: int) -> None:
        ts = self._now_ts()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id
            FROM subscriptions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if row is None:
            conn.close()
            return
        sub_id = row[0]
        cursor.execute(
            """
            UPDATE subscriptions
            SET status = ?, canceled_at = ?, updated_at = ?
            WHERE id = ?
            """,
            ("canceled", ts, ts, sub_id),
        )
        conn.commit()
        conn.close()
        logger.info("Subscription %s for user %s canceled", sub_id, user_id)


def run_billing() -> None:
    service = SubscriptionService()
    service.run_billing_once()

