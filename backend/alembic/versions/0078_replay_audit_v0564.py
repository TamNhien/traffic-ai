"""Deterministic crossing refinement and matching evidence V0.5.64.

Revision ID: 0078_replay_audit_v0564
Revises: 0077_delivery_prescan_v0563
"""
from alembic import op
import sqlalchemy as sa

revision = "0078_replay_audit_v0564"
down_revision = "0077_delivery_prescan_v0563"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.64', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.63', updated_at=now() WHERE key='schema_version'"))
