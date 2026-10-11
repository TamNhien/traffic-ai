"""V0.5.79 consistent release metadata; no table or counting changes."""
from alembic import op
import sqlalchemy as sa

revision = "0093_version_contract_v0579"
down_revision = "0092_direct_shadow_v0578"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.79', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.78', updated_at=now() WHERE key='schema_version'"))
