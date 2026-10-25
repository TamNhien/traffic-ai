"""V0.5.117 runtime upgrade; release metadata only."""
from alembic import op
import sqlalchemy as sa

revision = '0131_runtime_status_v05117'
down_revision = '0130_target_evidence_v05116'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.117', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.116', updated_at=now() WHERE key='schema_version'"))
