"""V0.5.90: AI-only verified export comparison and post-GT download UX."""
from alembic import op
import sqlalchemy as sa

revision = "0104_ai_export_v0590"
down_revision = "0103_release_eol_v0589"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.90', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.89', updated_at=now() WHERE key='schema_version'"))
