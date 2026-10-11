"""V0.5.78 bounded direct/direct duplicate closure (version metadata only)."""
from alembic import op
import sqlalchemy as sa

revision = "0092_direct_shadow_v0578"
down_revision = "0091_gt_forensics_v0577"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.78', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.77', updated_at=now() WHERE key='schema_version'"))
