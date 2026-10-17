"""Counting stability and HumanGuard decision audit V0.5.94."""
from alembic import op
import sqlalchemy as sa

revision = "0108_guard_audit_v0594"
down_revision = "0107_reports_guard_v0593"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.94', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.93', updated_at=now() WHERE key='schema_version'"))
