"""Session-scoped counters and Smart Gate 3.0 defaults.

Revision ID: 0009_session_realtime_v3
Revises: 0008_smart_gate_v2
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_session_realtime_v3"
down_revision = "0008_smart_gate_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only migrate cameras that still use the previous untouched V0.3.0 default.
    # Explicit values chosen by the user remain unchanged.
    op.execute(sa.text("UPDATE cameras SET confidence_threshold=0.20 WHERE ABS(confidence_threshold - 0.25) < 0.000001"))
    op.execute(sa.text("UPDATE system_settings SET value='0.3.1', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.3.0', updated_at=now() WHERE key='schema_version'"))
