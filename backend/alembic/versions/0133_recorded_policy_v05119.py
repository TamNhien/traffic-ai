"""V0.5.119 recorded policy display; release metadata only."""
from alembic import op
import sqlalchemy as sa

revision = '0133_recorded_policy_v05119'
down_revision = '0132_runtime_policy_v05118'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.119', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.118', updated_at=now() WHERE key='schema_version'"))
