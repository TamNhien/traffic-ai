"""V0.5.106 finite endpoint precision experiment; metadata only."""
from alembic import op
import sqlalchemy as sa

revision = "0120_endpoint_precision_v05106"
down_revision = "0119_trace_attest_v05105"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.106', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.105', updated_at=now() WHERE key='schema_version'"))
