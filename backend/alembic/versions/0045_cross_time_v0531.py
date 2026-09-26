"""Geometric crossing timestamp + startup ghost guard V0.5.31.

Revision ID: 0045_cross_time_v0531
Revises: 0044_truck_lock_v0530
"""
from alembic import op
import sqlalchemy as sa

revision = "0045_cross_time_v0531"
down_revision = "0044_truck_lock_v0530"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.31', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.30', updated_at=now() WHERE key='schema_version'"))
