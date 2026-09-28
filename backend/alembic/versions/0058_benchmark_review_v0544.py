"""Benchmark Review 9.0 + passage delivery semantics V0.5.44.

Revision ID: 0058_benchmark_review_v0544
Revises: 0057_cross_closure_v0543
"""
from alembic import op
import sqlalchemy as sa

revision = "0058_benchmark_review_v0544"
down_revision = "0057_cross_closure_v0543"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.44', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.43', updated_at=now() WHERE key='schema_version'"))
