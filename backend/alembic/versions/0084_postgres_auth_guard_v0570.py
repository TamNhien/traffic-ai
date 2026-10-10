"""PostgreSQL persisted-role credential guard V0.5.70.

Revision ID: 0084_postgres_auth_guard_v0570
Revises: 0083_bounded_startup_v0569
"""
from alembic import op
import sqlalchemy as sa

revision = "0084_postgres_auth_guard_v0570"
down_revision = "0083_bounded_startup_v0569"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.70', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.69', updated_at=now() WHERE key='schema_version'"))
