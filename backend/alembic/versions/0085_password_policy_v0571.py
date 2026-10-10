"""Account password policy and security UX V0.5.71 (metadata-only migration).

Revision ID: 0085_password_policy_v0571
Revises: 0084_postgres_auth_guard_v0570
"""
from alembic import op
import sqlalchemy as sa

revision = "0085_password_policy_v0571"
down_revision = "0084_postgres_auth_guard_v0570"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.71', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.70', updated_at=now() WHERE key='schema_version'"))
