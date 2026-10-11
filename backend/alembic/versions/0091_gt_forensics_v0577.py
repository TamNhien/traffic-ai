"""V0.5.77 startup path & offline GT forensic audit (metadata only)."""
from alembic import op
import sqlalchemy as sa

revision = "0091_gt_forensics_v0577"
down_revision = "0090_ci_token_v0576"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.77', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.76', updated_at=now() WHERE key='schema_version'"))
