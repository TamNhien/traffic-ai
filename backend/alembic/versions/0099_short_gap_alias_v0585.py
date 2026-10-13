"""V0.5.85: short-gap alias continuity guard; metadata-only migration."""
from alembic import op
import sqlalchemy as sa
revision = "0099_short_gap_alias_v0585"
down_revision = "0098_raw_provenance_v0584"
branch_labels = None
depends_on = None
def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.85', updated_at=now() WHERE key='schema_version'"))
def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.84', updated_at=now() WHERE key='schema_version'"))
