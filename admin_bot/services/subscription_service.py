from __future__ import annotations

from payment_bot.services.sync_service import SubscriptionSyncService

from admin_bot.db.database import Database
from admin_bot.db.repositories import AdminActionRepository, PaymentBotRepository
from admin_bot.services.role_service import RoleService


class SubscriptionService:
    def __init__(self, *, db: Database, roles: RoleService) -> None:
        self._db = db
        self._roles = roles

    async def grant_lifetime(
        self,
        *,
        actor_telegram_user_id: int,
        target_telegram_user_id: int,
    ) -> None:
        role = await self._roles.require_access(actor_telegram_user_id)
        if not self._roles.can_manage_subscriptions(role):
            raise PermissionError("Недостаточно прав для выдачи доступа")
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            pb = PaymentBotRepository(conn)
            audit = AdminActionRepository(conn)
            user = await pb.find_user_by_telegram_id(target_telegram_user_id)
            if not user:
                raise ValueError("Пользователь не найден в payment_bot")
            sub_before = await pb.get_subscription_by_user_id(int(user["id"]))
            sub_after = await pb.manual_grant_subscription(
                user_id=int(user["id"]),
                days=0,
                revoke_source=f"admin_bot:{actor_telegram_user_id}",
            )
            SubscriptionSyncService.sync_subscription_to_main_bot(
                user_telegram_id=target_telegram_user_id,
                status=str(sub_after["status"]),
                paid_until=sub_after["paid_until"],
                canceled_at=sub_after.get("canceled_at"),
            )
            await audit.log_action(
                admin_telegram_user_id=actor_telegram_user_id,
                target_telegram_user_id=target_telegram_user_id,
                action="subscription_grant_lifetime",
                before=dict(sub_before) if sub_before else {},
                after=dict(sub_after) if sub_after else {},
            )

    async def grant_days(
        self,
        *,
        actor_telegram_user_id: int,
        target_telegram_user_id: int,
        days: int,
    ) -> None:
        del days
        await self.grant_lifetime(
            actor_telegram_user_id=actor_telegram_user_id,
            target_telegram_user_id=target_telegram_user_id,
        )

    async def revoke(
        self,
        *,
        actor_telegram_user_id: int,
        target_telegram_user_id: int,
    ) -> None:
        role = await self._roles.require_access(actor_telegram_user_id)
        if not self._roles.can_manage_subscriptions(role):
            raise PermissionError("Недостаточно прав для отзыва доступа")
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            pb = PaymentBotRepository(conn)
            audit = AdminActionRepository(conn)
            user = await pb.find_user_by_telegram_id(target_telegram_user_id)
            if not user:
                raise ValueError("Пользователь не найден в payment_bot")
            sub_before = await pb.get_subscription_by_user_id(int(user["id"]))
            sub_after = await pb.manual_revoke_subscription(
                user_id=int(user["id"]),
                revoke_source=f"admin_bot:{actor_telegram_user_id}",
            )
            SubscriptionSyncService.sync_subscription_to_main_bot(
                user_telegram_id=target_telegram_user_id,
                status="inactive",
                paid_until=sub_after["paid_until"] if sub_after else None,
                canceled_at=sub_after.get("canceled_at") if sub_after else None,
            )
            await audit.log_action(
                admin_telegram_user_id=actor_telegram_user_id,
                target_telegram_user_id=target_telegram_user_id,
                action="subscription_revoke",
                before=dict(sub_before) if sub_before else {},
                after=dict(sub_after) if sub_after else {},
            )

    async def set_expired(
        self,
        *,
        actor_telegram_user_id: int,
        target_telegram_user_id: int,
    ) -> None:
        role = await self._roles.require_access(actor_telegram_user_id)
        if not self._roles.can_manage_subscriptions(role):
            raise PermissionError("Недостаточно прав")
        if not self._db.pool:
            raise RuntimeError("DB not connected")
        async with self._db.pool.acquire() as conn:
            pb = PaymentBotRepository(conn)
            audit = AdminActionRepository(conn)
            user = await pb.find_user_by_telegram_id(target_telegram_user_id)
            if not user:
                raise ValueError("Пользователь не найден в payment_bot")
            sub_before = await pb.get_subscription_by_user_id(int(user["id"]))
            sub_after = await pb.set_expired(
                user_id=int(user["id"]),
                revoke_source=f"admin_bot:{actor_telegram_user_id}",
            )
            SubscriptionSyncService.sync_subscription_to_main_bot(
                user_telegram_id=target_telegram_user_id,
                status="expired",
                paid_until=sub_after["paid_until"] if sub_after else None,
                canceled_at=sub_after.get("canceled_at") if sub_after else None,
            )
            await audit.log_action(
                admin_telegram_user_id=actor_telegram_user_id,
                target_telegram_user_id=target_telegram_user_id,
                action="subscription_set_expired",
                before=dict(sub_before) if sub_before else {},
                after=dict(sub_after) if sub_after else {},
            )
