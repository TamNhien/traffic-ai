"""V0.5.83: direction-aware benchmark evidence; metadata only."""
from alembic import op
import sqlalchemy as sa

revision = "0097_direction_audit_v0583"
down_revision = "0096_raw_id_reuse_v0582"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.83', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.82', updated_at=now() WHERE key='schema_version'"))
