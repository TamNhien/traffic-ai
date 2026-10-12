"""V0.5.80 incumbent identity preclaim; version-only migration."""
from alembic import op
import sqlalchemy as sa

revision = "0094_incumbent_identity_v0580"
down_revision = "0093_version_contract_v0579"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.80', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.79', updated_at=now() WHERE key='schema_version'"))
