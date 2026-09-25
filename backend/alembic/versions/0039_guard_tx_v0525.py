"""Transactional Human Guard 2.1 + Crossing Engine 7.2 V0.5.25.

Revision ID: 0039_guard_tx_v0525
Revises: 0038_rider_guard_v0524
"""
from alembic import op
import sqlalchemy as sa

revision = "0039_guard_tx_v0525"
down_revision = "0038_rider_guard_v0524"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.25', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.24', updated_at=now() WHERE key='schema_version'"))
