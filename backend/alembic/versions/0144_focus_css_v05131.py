"""V0.5.131: restore dark focus button CSS, metadata only."""
from alembic import op
import sqlalchemy as sa

revision = '0144_focus_css_v05131'
down_revision = '0143_local_trend_v05130'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.131', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.130', updated_at=now() WHERE key='schema_version'"))
