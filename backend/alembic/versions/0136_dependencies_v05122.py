"""V0.5.122 dependency and runtime upgrade; release metadata only."""
from alembic import op
import sqlalchemy as sa

revision = '0136_dependencies_v05122'
down_revision = '0135_frontend_pin_v05121'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.122', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.121', updated_at=now() WHERE key='schema_version'"))
