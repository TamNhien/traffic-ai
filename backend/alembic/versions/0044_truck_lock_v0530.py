"""Truck Semantic Lock + canonical four-wheel fusion V0.5.30.

Revision ID: 0044_truck_lock_v0530
Revises: 0043_heavy_track_v0529
"""
from alembic import op
import sqlalchemy as sa

revision = "0044_truck_lock_v0530"
down_revision = "0043_heavy_track_v0529"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.30', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.29', updated_at=now() WHERE key='schema_version'"))
