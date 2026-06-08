from __future__ import annotations

from dataclasses import dataclass

from admin_bot.db.database import Database
from admin_bot.db.repositories import AdminUserRepository


@dataclass(frozen=True)
class AdminRole:
    code: str
    title_ru: str


ROLES = {
    "owner": AdminRole(code="owner", title_ru="владелец"),
    "admin": AdminRole(code="admin", title_ru="администратор"),
    "support": AdminRole(code="support", title_ru="поддержка"),
    "viewer": AdminRole(code="viewer", title_ru="наблюдатель"),
}


class RoleService:
    def __init__(self, *, db: Database, owner_telegram_id: int) -> None:
        self._db = db
        self._owner_telegram_id = owner_telegram_id

    async def ensure_owner_seeded(self, *, username: str | None) -> None:
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            repo = AdminUserRepository(conn)
            await repo.upsert_owner(self._owner_telegram_id, username)

    async def get_admin_user(self, telegram_user_id: int):
        if telegram_user_id == self._owner_telegram_id:
            # Owner can always pass gate; but we still prefer row for notify flags.
            pass
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            repo = AdminUserRepository(conn)
            return await repo.get_by_telegram_id(telegram_user_id)

    async def require_access(self, telegram_user_id: int) -> str:
        row = await self.get_admin_user(telegram_user_id)
        if row and bool(row["is_active"]):
            role = str(row["role"] or "")
            if role in ROLES:
                return role
        if telegram_user_id == self._owner_telegram_id:
            return "owner"
        raise PermissionError("Нет доступа к админ-боту")

    async def require_role(self, telegram_user_id: int, allowed: set[str]) -> str:
        role = await self.require_access(telegram_user_id)
        if role not in allowed:
            raise PermissionError("Недостаточно прав")
        return role

    @staticmethod
    def can_view_raw_payments(role: str) -> bool:
        return role in {"owner", "admin"}

    @staticmethod
    def can_manage_roles(role: str) -> bool:
        return role == "owner"

    @staticmethod
    def can_manage_subscriptions(role: str) -> bool:
        return role in {"owner", "admin"}

    @staticmethod
    def can_view_payments(role: str) -> bool:
        return role in {"owner", "admin"}

    @staticmethod
    def can_view_users(role: str) -> bool:
        return role in {"owner", "admin", "support", "viewer"}

