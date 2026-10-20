"""V0.5.110 trace recovery pipeline; no event or Ground Truth edits."""
from alembic import op
import sqlalchemy as sa
revision = "0124_trace_recovery_v05110"
down_revision = "0123_road_probe_v05109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.110', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.109', updated_at=now() WHERE key='schema_version'"))
