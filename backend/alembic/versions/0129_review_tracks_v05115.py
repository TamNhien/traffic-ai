"""V0.5.115 verified review track overlay tool (release metadata only)."""
from alembic import op
import sqlalchemy as sa

revision = '0129_review_tracks_v05115'
down_revision = '0128_review_mount_v05114'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.115', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.114', updated_at=now() WHERE key='schema_version'"))
