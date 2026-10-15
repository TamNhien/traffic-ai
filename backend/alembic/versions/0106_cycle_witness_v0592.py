"""V0.5.92 read-only canonical crossing-cycle witness release metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0106_cycle_witness_v0592"
down_revision = "0105_review_nav_v0591"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.92', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.91', updated_at=now() WHERE key='schema_version'"))
