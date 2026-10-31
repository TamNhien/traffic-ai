"""V0.5.132: verified camera evidence review; metadata only, no business data changed."""
from alembic import op
import sqlalchemy as sa

revision = '0145_camera_evidence_v05132'
down_revision = '0144_focus_css_v05131'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.132', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.131', updated_at=now() WHERE key='schema_version'"))
