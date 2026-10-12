"""V0.5.82: narrow raw-ID teleport guard; metadata-only migration."""
from alembic import op
import sqlalchemy as sa

revision = "0096_raw_id_reuse_v0582"
down_revision = "0095_quiet_startup_v0581"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.82', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.81', updated_at=now() WHERE key='schema_version'"))
