"""Instant Overlay + Road ROI Tracking V0.5.13.

Revision ID: 0027_fast_overlay_v0513
Revises: 0026_road_guard_v0512
"""
from alembic import op
import sqlalchemy as sa

revision = "0027_fast_overlay_v0513"
down_revision = "0026_road_guard_v0512"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.13', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.12', updated_at=now() WHERE key='schema_version'"))
