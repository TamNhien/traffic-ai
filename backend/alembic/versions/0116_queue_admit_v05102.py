"""V0.5.102: deferred queue admission counter safety (no schema mutation)."""
from alembic import op
import sqlalchemy as sa

revision = "0116_queue_admit_v05102"
down_revision = "0115_guard_commit_v05101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.102', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.101', updated_at=now() WHERE key='schema_version'"))
