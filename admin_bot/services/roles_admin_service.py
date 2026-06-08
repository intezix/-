from __future__ import annotations

from admin_bot.db.database import Database
from admin_bot.db.repositories import AdminActionRepository, AdminUserRepository
from admin_bot.services.role_service import ROLES, RoleService


class RolesAdminService:
    def __init__(self, *, db: Database, roles: RoleService) -> None:
        self._db = db
        self._roles = roles

    async def create_or_update_admin(
        self,
        *,
        actor_telegram_user_id: int,
        target_telegram_user_id: int,
        role: str,
        username: str | None,
    ) -> None:
        actor_role = await self._roles.require_access(actor_telegram_user_id)
        if not self._roles.can_manage_roles(actor_role):
            raise PermissionError("Недостаточно прав")
        if role not in ROLES:
            raise ValueError("Некорректная роль")
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            repo = AdminUserRepository(conn)
            audit = AdminActionRepository(conn)
            before = await repo.get_by_telegram_id(target_telegram_user_id)
            await repo.create_admin(target_telegram_user_id, username=username, role=role, created_by=actor_telegram_user_id)
            after = await repo.get_by_telegram_id(target_telegram_user_id)
            await audit.log_action(
                admin_telegram_user_id=actor_telegram_user_id,
                target_telegram_user_id=target_telegram_user_id,
                action="admin_user_upsert",
                before=dict(before) if before else {},
                after=dict(after) if after else {},
            )

    async def set_role(
        self,
        *,
        actor_telegram_user_id: int,
        target_telegram_user_id: int,
        role: str,
    ) -> None:
        actor_role = await self._roles.require_access(actor_telegram_user_id)
        if not self._roles.can_manage_roles(actor_role):
            raise PermissionError("Недостаточно прав")
        if role not in ROLES:
            raise ValueError("Некорректная роль")
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            repo = AdminUserRepository(conn)
            audit = AdminActionRepository(conn)
            before = await repo.get_by_telegram_id(target_telegram_user_id)
            await repo.set_role(target_telegram_user_id, role)
            after = await repo.get_by_telegram_id(target_telegram_user_id)
            await audit.log_action(
                admin_telegram_user_id=actor_telegram_user_id,
                target_telegram_user_id=target_telegram_user_id,
                action="admin_user_set_role",
                before=dict(before) if before else {},
                after=dict(after) if after else {},
            )

    async def set_active(
        self,
        *,
        actor_telegram_user_id: int,
        target_telegram_user_id: int,
        is_active: bool,
    ) -> None:
        actor_role = await self._roles.require_access(actor_telegram_user_id)
        if not self._roles.can_manage_roles(actor_role):
            raise PermissionError("Недостаточно прав")
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            repo = AdminUserRepository(conn)
            audit = AdminActionRepository(conn)
            before = await repo.get_by_telegram_id(target_telegram_user_id)
            await repo.set_active(target_telegram_user_id, is_active)
            after = await repo.get_by_telegram_id(target_telegram_user_id)
            await audit.log_action(
                admin_telegram_user_id=actor_telegram_user_id,
                target_telegram_user_id=target_telegram_user_id,
                action="admin_user_set_active",
                before=dict(before) if before else {},
                after=dict(after) if after else {},
            )

    async def set_notify_enabled(
        self,
        *,
        actor_telegram_user_id: int,
        target_telegram_user_id: int,
        notify_enabled: bool,
    ) -> None:
        actor_role = await self._roles.require_access(actor_telegram_user_id)
        if not self._roles.can_manage_roles(actor_role):
            raise PermissionError("Недостаточно прав")
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            repo = AdminUserRepository(conn)
            audit = AdminActionRepository(conn)
            before = await repo.get_by_telegram_id(target_telegram_user_id)
            await repo.set_notify_flags(target_telegram_user_id, notify_enabled=notify_enabled)
            after = await repo.get_by_telegram_id(target_telegram_user_id)
            await audit.log_action(
                admin_telegram_user_id=actor_telegram_user_id,
                target_telegram_user_id=target_telegram_user_id,
                action="admin_user_set_notify",
                before=dict(before) if before else {},
                after=dict(after) if after else {},
            )

