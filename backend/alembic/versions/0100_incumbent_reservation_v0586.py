"""V0.5.86: visible incumbent reservation and dashboard UX; metadata only."""
from alembic import op
import sqlalchemy as sa
revision = "0100_incumbent_reservation_v0586"
down_revision = "0099_short_gap_alias_v0585"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.86', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.85', updated_at=now() WHERE key='schema_version'"))
