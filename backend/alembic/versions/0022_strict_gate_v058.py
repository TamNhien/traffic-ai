"""Strict finite gate + fast crossing runtime V0.5.8.

Revision ID: 0022_strict_gate_v058
Revises: 0021_annotation_ux_v057
"""
from alembic import op
import sqlalchemy as sa

revision = "0022_strict_gate_v058"
down_revision = "0021_annotation_ux_v057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE cameras ALTER COLUMN confidence_threshold SET DEFAULT 0.12"))
    op.execute(sa.text("UPDATE cameras SET confidence_threshold=0.12 WHERE ABS(confidence_threshold - 0.18) < 0.000001"))
    op.execute(sa.text("UPDATE system_settings SET value='0.5.8', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE cameras ALTER COLUMN confidence_threshold SET DEFAULT 0.18"))
    op.execute(sa.text("UPDATE cameras SET confidence_threshold=0.18 WHERE ABS(confidence_threshold - 0.12) < 0.000001"))
    op.execute(sa.text("UPDATE system_settings SET value='0.5.7', updated_at=now() WHERE key='schema_version'"))
