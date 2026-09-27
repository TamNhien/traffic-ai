"""Near-margin bicycle context + ultra-spatial rescue signature V0.5.38.

Revision ID: 0052_bike_ultra_v0538
Revises: 0051_bike_comp_v0537
"""
from alembic import op
import sqlalchemy as sa

revision = "0052_bike_ultra_v0538"
down_revision = "0051_bike_comp_v0537"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.38', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.37', updated_at=now() WHERE key='schema_version'"))
