"""Hybrid high-recall detector + tracker rescue V0.5.15.

Revision ID: 0029_hybrid_recall_v0515
Revises: 0028_full_detect_v0514
"""
from alembic import op
import sqlalchemy as sa

revision = "0029_hybrid_recall_v0515"
down_revision = "0028_full_detect_v0514"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE cameras ALTER COLUMN confidence_threshold SET DEFAULT 0.06"))
    op.execute(sa.text("UPDATE cameras SET confidence_threshold=0.06 WHERE ABS(confidence_threshold - 0.12) < 0.000001"))
    op.execute(sa.text("UPDATE system_settings SET value='0.5.15', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE cameras ALTER COLUMN confidence_threshold SET DEFAULT 0.12"))
    op.execute(sa.text("UPDATE cameras SET confidence_threshold=0.12 WHERE ABS(confidence_threshold - 0.06) < 0.000001"))
    op.execute(sa.text("UPDATE system_settings SET value='0.5.14', updated_at=now() WHERE key='schema_version'"))
