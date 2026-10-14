"""V0.5.89: release line-ending packaging and conflict diagnostics; metadata only."""
from alembic import op
import sqlalchemy as sa

revision = "0103_release_eol_v0589"
down_revision = "0102_temporal_review_v0588"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.89', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.88', updated_at=now() WHERE key='schema_version'"))
