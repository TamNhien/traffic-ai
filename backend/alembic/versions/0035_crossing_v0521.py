"""Crossing Engine 7.0 + benchmark reconcile V0.5.21.

Revision ID: 0035_crossing_v0521
Revises: 0034_benchmark_overlay_v0520
"""
from alembic import op
import sqlalchemy as sa

revision = "0035_crossing_v0521"
down_revision = "0034_benchmark_overlay_v0520"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.21', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.20', updated_at=now() WHERE key='schema_version'"))
