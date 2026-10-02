"""Geometry + Semantic Shadow Closure 9.6 V0.5.50.

Revision ID: 0064_geometry_semantic_v0550
Revises: 0063_precision_recovery_v0549
"""
from alembic import op
import sqlalchemy as sa

revision = "0064_geometry_semantic_v0550"
down_revision = "0063_precision_recovery_v0549"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.50', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.49', updated_at=now() WHERE key='schema_version'"))
