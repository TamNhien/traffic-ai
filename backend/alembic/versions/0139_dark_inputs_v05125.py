"""Traffic AI V0.5.125: unified dark form controls; schema metadata only."""
from alembic import op
import sqlalchemy as sa

revision = '0139_dark_inputs_v05125'
down_revision = '0138_npm_contract_v05124'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.125', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.124', updated_at=now() WHERE key='schema_version'"))
