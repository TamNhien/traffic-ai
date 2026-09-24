"""Single-Object heavy vehicle guard V0.5.17.

Revision ID: 0031_single_vehicle_v0517
Revises: 0030_auto_road_v0516
"""
from alembic import op
import sqlalchemy as sa

revision = "0031_single_vehicle_v0517"
down_revision = "0030_auto_road_v0516"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.17', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.16', updated_at=now() WHERE key='schema_version'"))
