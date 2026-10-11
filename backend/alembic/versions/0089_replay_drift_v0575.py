"""V0.5.75: version bump for read-only offline replay diagnostics.

No counting tables, GT, user data, backup catalog or algorithm parameters change.
"""
from alembic import op
import sqlalchemy as sa

revision = "0089_replay_drift_v0575"
down_revision = "0088_backup_scheduler_v0574"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.75', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.74', updated_at=now() WHERE key='schema_version'"))
