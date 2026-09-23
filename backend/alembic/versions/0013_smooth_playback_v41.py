"""Smooth Playback 4.1 runtime marker.

Revision ID: 0013_smooth_playback_v41
Revises: 0012_realtime_gate_v4
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_smooth_playback_v41"
down_revision = "0012_realtime_gate_v4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.4.1', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.4.0', updated_at=now() WHERE key='schema_version'"))
