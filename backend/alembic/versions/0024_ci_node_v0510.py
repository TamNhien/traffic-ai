"""CI portability + Node/GitHub Actions refresh V0.5.10.

Revision ID: 0024_ci_node_v0510
Revises: 0023_clean_retrain_v059
"""
from alembic import op
import sqlalchemy as sa

revision = "0024_ci_node_v0510"
down_revision = "0023_clean_retrain_v059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.10', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.9', updated_at=now() WHERE key='schema_version'"))
