"""V0.5.123 CI Node contract and publish-version safety; metadata only."""
from alembic import op
import sqlalchemy as sa

revision = '0137_ci_publish_guard_v05123'
down_revision = '0136_dependencies_v05122'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.123', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.122', updated_at=now() WHERE key='schema_version'"))
