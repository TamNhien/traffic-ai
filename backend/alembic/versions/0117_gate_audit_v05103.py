"""V0.5.103: verified gate-coverage offline audit; metadata only."""
from alembic import op
import sqlalchemy as sa

revision = "0117_gate_audit_v05103"
down_revision = "0116_queue_admit_v05102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.103', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.102', updated_at=now() WHERE key='schema_version'"))
