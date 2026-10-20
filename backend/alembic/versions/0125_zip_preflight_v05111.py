"""V0.5.111 local benchmark ZIP preflight; no data schema or count changes."""
from alembic import op
import sqlalchemy as sa

revision = "0125_zip_preflight_v05111"
down_revision = "0124_trace_recovery_v05110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.111', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.110', updated_at=now() WHERE key='schema_version'"))
