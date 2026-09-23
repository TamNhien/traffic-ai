"""Gateway runtime/Docker DNS hardening marker.

Revision ID: 0011_gateway_dns_runtime
Revises: 0010_runtime_hardening
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_gateway_dns_runtime"
down_revision = "0010_runtime_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Infrastructure-only release. Keep application schema marker aligned with source.
    op.execute(sa.text("UPDATE system_settings SET value='0.3.3', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.3.2', updated_at=now() WHERE key='schema_version'"))
