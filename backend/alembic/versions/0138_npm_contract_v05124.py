"""Traffic AI V0.5.124: dynamic npm pin contract; metadata only."""
from alembic import op
import sqlalchemy as sa

revision = '0138_npm_contract_v05124'
down_revision = '0137_ci_publish_guard_v05123'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.124', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.123', updated_at=now() WHERE key='schema_version'"))
