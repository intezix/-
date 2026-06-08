from __future__ import annotations

from aiogram.types import Message

from config import DEV_ADMIN_IDS


def is_dev_admin(user_id: int | None) -> bool:
    """Доступ к тестовым/служебным командам основного бота."""
    if user_id is None or not DEV_ADMIN_IDS:
        return False
    return user_id in DEV_ADMIN_IDS


def is_dev_admin_message(message: Message) -> bool:
    if not message.from_user:
        return False
    return is_dev_admin(message.from_user.id)
