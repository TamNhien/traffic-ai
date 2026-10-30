"""V0.5.126: Benchmark quality audit + consolidated docs; metadata-only migration."""
from alembic import op
import sqlalchemy as sa

revision = '0140_quality_audit_v05126'
down_revision = '0139_dark_inputs_v05125'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.126', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.125', updated_at=now() WHERE key='schema_version'"))
