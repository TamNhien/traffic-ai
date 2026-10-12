"""V0.5.84: per-raw provenance guard, metadata-only migration."""
from alembic import op
import sqlalchemy as sa

revision = "0098_raw_provenance_v0584"
down_revision = "0097_direction_audit_v0583"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.84', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.83', updated_at=now() WHERE key='schema_version'"))
