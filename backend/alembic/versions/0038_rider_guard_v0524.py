"""Rider-aware Human Guard 2.0 V0.5.24.

Revision ID: 0038_rider_guard_v0524
Revises: 0037_integrity_v0523
"""
from alembic import op
import sqlalchemy as sa

revision = "0038_rider_guard_v0524"
down_revision = "0037_integrity_v0523"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.24', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.23', updated_at=now() WHERE key='schema_version'"))
