"""V0.5.113 update frontend Vite security floor; metadata only."""
from alembic import op
import sqlalchemy as sa

revision = "0127_vite_security_v05113"
down_revision = "0126_review_frames_v05112"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.113', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.112', updated_at=now() WHERE key='schema_version'"))
