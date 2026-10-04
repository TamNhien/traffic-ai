"""Continuous Anchor and Benchmark Evidence V0.5.56.

Revision ID: 0070_benchmark_evidence_v0556
Revises: 0069_refine_admission_v0555
"""
from alembic import op
import sqlalchemy as sa

revision = "0070_benchmark_evidence_v0556"
down_revision = "0069_refine_admission_v0555"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.56', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.55', updated_at=now() WHERE key='schema_version'"))
