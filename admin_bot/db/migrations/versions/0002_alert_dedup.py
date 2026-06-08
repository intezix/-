"""Alert dedup table.

Revision ID: adm_0002
Revises: adm_0001
Create Date: 2026-05-01

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "adm_0002"
down_revision = "adm_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "adm_alert_dedup",
        sa.Column("fingerprint", sa.String(length=200), primary_key=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_adm_alert_dedup_last_sent", "adm_alert_dedup", ["last_sent_at"])


def downgrade() -> None:
    op.drop_index("ix_adm_alert_dedup_last_sent", table_name="adm_alert_dedup")
    op.drop_table("adm_alert_dedup")

