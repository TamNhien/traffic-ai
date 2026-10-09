"""Ground truth readiness for benchmark scoring V0.5.66.

Revision ID: 0080_benchmark_ready_v0566
Revises: 0079_van_semantics_v0565
"""
from alembic import op
import sqlalchemy as sa

revision = "0080_benchmark_ready_v0566"
down_revision = "0079_van_semantics_v0565"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.66', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.65', updated_at=now() WHERE key='schema_version'"))
