"""Docker readiness and diagnostic continuity V0.5.95."""
from alembic import op
import sqlalchemy as sa

revision = "0109_docker_guard_v0595"
down_revision = "0108_guard_audit_v0594"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.95', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.94', updated_at=now() WHERE key='schema_version'"))
