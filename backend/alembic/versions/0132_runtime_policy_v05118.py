"""V0.5.118 runtime policy upgrade; release metadata only."""
from alembic import op
import sqlalchemy as sa

revision = '0132_runtime_policy_v05118'
down_revision = '0131_runtime_status_v05117'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.118', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.117', updated_at=now() WHERE key='schema_version'"))
