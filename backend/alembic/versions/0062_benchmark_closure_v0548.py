"""Benchmark Closure 9.4 V0.5.48.

Revision ID: 0062_benchmark_closure_v0548
Revises: 0061_balanced_recall_v0547
"""
from alembic import op
import sqlalchemy as sa

revision = "0062_benchmark_closure_v0548"
down_revision = "0061_balanced_recall_v0547"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.48', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.47', updated_at=now() WHERE key='schema_version'"))
