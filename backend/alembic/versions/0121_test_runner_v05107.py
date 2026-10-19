"""V0.5.107 endpoint regression dependency fix; schema metadata only."""
from alembic import op
import sqlalchemy as sa

revision = "0121_test_runner_v05107"
down_revision = "0120_endpoint_precision_v05106"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.107', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.106', updated_at=now() WHERE key='schema_version'"))
