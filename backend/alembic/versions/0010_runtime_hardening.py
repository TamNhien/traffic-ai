"""Runtime script hardening and application schema marker.

Revision ID: 0010_runtime_hardening
Revises: 0009_session_realtime_v3
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_runtime_hardening"
down_revision = "0009_session_realtime_v3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No structural database change in V0.3.2. Keep the application schema marker
    # aligned with the released source/runtime contract.
    op.execute(sa.text("UPDATE system_settings SET value='0.3.2', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.3.1', updated_at=now() WHERE key='schema_version'"))
