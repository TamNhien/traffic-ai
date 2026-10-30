"""V0.5.128: Fix isolated repeatability test runner; metadata only."""
from alembic import op
import sqlalchemy as sa

revision = '0142_repeatability_runner_v05128'
down_revision = '0141_repeatability_v05127'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.128', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.127', updated_at=now() WHERE key='schema_version'"))
