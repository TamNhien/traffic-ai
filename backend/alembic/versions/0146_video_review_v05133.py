"""V0.5.133: local video review clips; metadata only, production data unchanged."""
from alembic import op
import sqlalchemy as sa

revision = '0146_video_review_v05133'
down_revision = '0145_camera_evidence_v05132'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.133', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.132', updated_at=now() WHERE key='schema_version'"))
