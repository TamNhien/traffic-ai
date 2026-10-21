"""V0.5.112 offline visual review frame export. No counting or database schema changes."""
from alembic import op
import sqlalchemy as sa

revision = "0126_review_frames_v05112"
down_revision = "0125_zip_preflight_v05111"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.112', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.111', updated_at=now() WHERE key='schema_version'"))
