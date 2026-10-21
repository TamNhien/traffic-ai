"""V0.5.114 review exporter verified Docker mount closure (metadata only)."""
from alembic import op
import sqlalchemy as sa

revision = "0128_review_mount_v05114"
down_revision = "0127_vite_security_v05113"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.114', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.113', updated_at=now() WHERE key='schema_version'"))
