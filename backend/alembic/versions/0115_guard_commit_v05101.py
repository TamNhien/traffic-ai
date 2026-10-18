"""V0.5.101: deferred guard commit safety release marker (no data mutation)."""
from alembic import op
import sqlalchemy as sa

revision = "0115_guard_commit_v05101"
down_revision = "0114_raw_handoff_v05100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.101', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.100', updated_at=now() WHERE key='schema_version'"))
