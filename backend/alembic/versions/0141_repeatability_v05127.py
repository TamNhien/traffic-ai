"""V0.5.127 benchmark repeatability diagnostics; metadata-only migration."""
from alembic import op
import sqlalchemy as sa

revision = '0141_repeatability_v05127'
down_revision = '0140_quality_audit_v05126'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.127', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.126', updated_at=now() WHERE key='schema_version'"))
