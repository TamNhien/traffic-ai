"""Isolated Python test cache V0.5.96."""
from alembic import op
import sqlalchemy as sa

revision = "0110_pycache_v0596"
down_revision = "0109_docker_guard_v0595"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.96', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.95', updated_at=now() WHERE key='schema_version'"))
