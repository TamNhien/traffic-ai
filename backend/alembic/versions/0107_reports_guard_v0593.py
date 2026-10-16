"""Traffic reports and contradictory short-gap alias guard V0.5.93."""
from alembic import op
import sqlalchemy as sa

revision = "0107_reports_guard_v0593"
down_revision = "0106_cycle_witness_v0592"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.93', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.92', updated_at=now() WHERE key='schema_version'"))
