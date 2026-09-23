"""UI cleanup and test harness hardening V0.5.1.

Revision ID: 0015_ui_test_hardening_v051
Revises: 0014_dataset_training_v50
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_ui_test_hardening_v051"
down_revision = "0014_dataset_training_v50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.1', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.0', updated_at=now() WHERE key='schema_version'"))
