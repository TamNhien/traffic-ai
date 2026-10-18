"""V0.5.105: trace/runtime provenance only; no user-data changes."""
from alembic import op
import sqlalchemy as sa

revision = "0119_trace_attest_v05105"
down_revision = "0118_gate_decision_v05104"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.105', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.104', updated_at=now() WHERE key='schema_version'"))
