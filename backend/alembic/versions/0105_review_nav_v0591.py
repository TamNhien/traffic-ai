"""V0.5.91: read-only benchmark timecode review navigation metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0105_review_nav_v0591"
down_revision = "0104_ai_export_v0590"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.91', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.90', updated_at=now() WHERE key='schema_version'"))
