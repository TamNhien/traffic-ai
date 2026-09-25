"""Dual Refiner Consensus 4.0 + Benchmark Global Match V0.5.27.

Revision ID: 0041_dual_refiner_v0527
Revises: 0040_class_refiner_v0526
"""
from alembic import op
import sqlalchemy as sa

revision = "0041_dual_refiner_v0527"
down_revision = "0040_class_refiner_v0526"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.27', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.26', updated_at=now() WHERE key='schema_version'"))
