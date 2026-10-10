"""Bounded startup diagnostics V0.5.69.

Revision ID: 0083_bounded_startup_v0569
Revises: 0082_security_auth_v0568
"""
from alembic import op
import sqlalchemy as sa

revision = "0083_bounded_startup_v0569"
down_revision = "0082_security_auth_v0568"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.69', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.68', updated_at=now() WHERE key='schema_version'"))
