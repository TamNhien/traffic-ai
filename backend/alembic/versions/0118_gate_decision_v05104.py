"""V0.5.104: per-track primary gate decision trace; metadata only."""
from alembic import op
import sqlalchemy as sa

revision = "0118_gate_decision_v05104"
down_revision = "0117_gate_audit_v05103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.104', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.103', updated_at=now() WHERE key='schema_version'"))
