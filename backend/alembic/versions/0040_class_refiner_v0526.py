"""Target-aware Class Refiner 3.0 + Video Start Rescue V0.5.26.

Revision ID: 0040_class_refiner_v0526
Revises: 0039_guard_tx_v0525
"""
from alembic import op
import sqlalchemy as sa

revision = "0040_class_refiner_v0526"
down_revision = "0039_guard_tx_v0525"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.26', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.25', updated_at=now() WHERE key='schema_version'"))
