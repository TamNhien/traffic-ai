"""V0.5.130: local-only benchmark trend audit and review navigation; metadata only."""
from alembic import op
import sqlalchemy as sa

revision = '0143_local_trend_v05130'
down_revision = '0142_repeatability_runner_v05128'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.130', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.128', updated_at=now() WHERE key='schema_version'"))
