"""Clean retrain + smart review workflow V0.5.9.

Revision ID: 0023_clean_retrain_v059
Revises: 0022_strict_gate_v058
"""
from alembic import op
import sqlalchemy as sa

revision = "0023_clean_retrain_v059"
down_revision = "0022_strict_gate_v058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.9', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.8', updated_at=now() WHERE key='schema_version'"))
