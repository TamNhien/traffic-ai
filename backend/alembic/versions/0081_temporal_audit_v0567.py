"""Temporal assignment evidence, read-only benchmark audit V0.5.67.

Revision ID: 0081_temporal_audit_v0567
Revises: 0080_benchmark_ready_v0566
"""
from alembic import op
import sqlalchemy as sa

revision = "0081_temporal_audit_v0567"
down_revision = "0080_benchmark_ready_v0566"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.67', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.66', updated_at=now() WHERE key='schema_version'"))
