"""Admin tables + pb_events indexes.

Revision ID: adm_0001
Revises: None
Create Date: 2026-05-01

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "adm_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "adm_admin_users",
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notify_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notify_errors", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notify_health", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
    )

    op.create_table(
        "adm_admin_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("admin_telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("target_telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("after_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_adm_actions_target_created", "adm_admin_actions", ["target_telegram_user_id", "created_at"])
    op.create_index("ix_adm_actions_admin_created", "adm_admin_actions", ["admin_telegram_user_id", "created_at"])

    op.create_table(
        "adm_user_overrides",
        sa.Column("telegram_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_adm_overrides_expires", "adm_user_overrides", ["expires_at"])

    # pb_events is the single event store. Add helpful indexes on payload_json fields.
    # Use expression indexes so we don't need to alter pb_events table shape.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pb_events_tg_user_created
        ON pb_events (((payload_json->>'telegram_user_id')::bigint), created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pb_events_source_created
        ON pb_events ((payload_json->>'source_bot'), created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pb_events_status_created
        ON pb_events ((payload_json->>'status'), created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_pb_events_errors_created
        ON pb_events (created_at DESC)
        WHERE (payload_json->>'status') = 'error'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_pb_events_errors_created")
    op.execute("DROP INDEX IF EXISTS ix_pb_events_status_created")
    op.execute("DROP INDEX IF EXISTS ix_pb_events_source_created")
    op.execute("DROP INDEX IF EXISTS ix_pb_events_tg_user_created")
    op.drop_index("ix_adm_overrides_expires", table_name="adm_user_overrides")
    op.drop_table("adm_user_overrides")
    op.drop_index("ix_adm_actions_admin_created", table_name="adm_admin_actions")
    op.drop_index("ix_adm_actions_target_created", table_name="adm_admin_actions")
    op.drop_table("adm_admin_actions")
    op.drop_table("adm_admin_users")

