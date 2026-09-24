"""Crossing Engine 6.0 telemetry V0.5.18.

Revision ID: 0032_crossing_engine_v0518
Revises: 0031_single_vehicle_v0517
"""
from alembic import op
import sqlalchemy as sa

revision = "0032_crossing_engine_v0518"
down_revision = "0031_single_vehicle_v0517"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.18', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.17', updated_at=now() WHERE key='schema_version'"))
