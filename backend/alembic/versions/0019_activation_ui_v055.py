"""Activation reliability and UI separation V0.5.5.

Revision ID: 0019_activation_ui_v055
Revises: 0018_alembic_guard_v054
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_activation_ui_v055"
down_revision = "0018_alembic_guard_v054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.5', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.4', updated_at=now() WHERE key='schema_version'"))
