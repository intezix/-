from __future__ import annotations

from dataclasses import dataclass

from admin_bot.config import Settings
from admin_bot.db.database import Database
from admin_bot.services.alert_service import AlertService
from admin_bot.services.broadcast_service import BroadcastService
from admin_bot.services.health_service import HealthService
from admin_bot.services.payment_service import PaymentService
from admin_bot.services.role_service import RoleService
from admin_bot.services.roles_admin_service import RolesAdminService
from admin_bot.services.stats_service import StatsService
from admin_bot.services.subscription_service import SubscriptionService
from admin_bot.services.system_service import SystemService
from admin_bot.services.user_service import UserService


@dataclass(frozen=True)
class AppContext:
    settings: Settings
    db: Database

    roles: RoleService
    roles_admin: RolesAdminService
    users: UserService
    subscriptions: SubscriptionService
    payments: PaymentService
    stats: StatsService
    health: HealthService
    alerts: AlertService
    system: SystemService
    broadcast: BroadcastService


async def build_app_context(settings: Settings) -> AppContext:
    db = Database(dsn=settings.postgres_dsn)
    await db.connect()

    roles = RoleService(db=db, owner_telegram_id=settings.owner_telegram_id)
    roles_admin = RolesAdminService(db=db, roles=roles)
    users = UserService(db=db, roles=roles)
    subscriptions = SubscriptionService(db=db, roles=roles)
    payments = PaymentService(db=db, roles=roles)
    stats = StatsService(db=db, roles=roles)
    health = HealthService(db=db, roles=roles, settings=settings)
    alerts = AlertService(db=db, roles=roles, settings=settings)
    system = SystemService(
        project_name=settings.docker_project_name,
        compose_dir=settings.docker_compose_dir,
    )
    broadcast = BroadcastService(
        db=db,
        roles=roles,
        payment_bot_token=settings.payment_bot_token,
    )

    return AppContext(
        settings=settings,
        db=db,
        roles=roles,
        roles_admin=roles_admin,
        users=users,
        subscriptions=subscriptions,
        payments=payments,
        stats=stats,
        health=health,
        alerts=alerts,
        system=system,
        broadcast=broadcast,
    )

