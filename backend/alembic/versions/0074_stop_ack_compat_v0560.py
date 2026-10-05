"""Stop acknowledgment compatibility V0.5.60.

Revision ID: 0074_stop_ack_compat_v0560
Revises: 0073_trace_identity_v0559
"""
from alembic import op
import sqlalchemy as sa

revision = "0074_stop_ack_compat_v0560"
down_revision = "0073_trace_identity_v0559"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.60', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.59', updated_at=now() WHERE key='schema_version'"))
