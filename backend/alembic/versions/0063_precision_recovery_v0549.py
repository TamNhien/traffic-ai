"""Precision Recovery Closure 9.5 V0.5.49.

Revision ID: 0063_precision_recovery_v0549
Revises: 0062_benchmark_closure_v0548
"""
from alembic import op
import sqlalchemy as sa

revision = "0063_precision_recovery_v0549"
down_revision = "0062_benchmark_closure_v0548"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.49', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.48', updated_at=now() WHERE key='schema_version'"))
