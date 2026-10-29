"""V0.5.120 per-raw motion review; release metadata only."""
from alembic import op
import sqlalchemy as sa

revision = '0134_raw_motion_audit_v05120'
down_revision = '0133_recorded_policy_v05119'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.120', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.119', updated_at=now() WHERE key='schema_version'"))
