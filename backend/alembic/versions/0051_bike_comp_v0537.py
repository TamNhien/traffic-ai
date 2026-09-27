"""Competitive bicycle context + spatial rescue signature V0.5.37.

Revision ID: 0051_bike_comp_v0537
Revises: 0050_bike_spatial_v0536
"""
from alembic import op
import sqlalchemy as sa

revision = "0051_bike_comp_v0537"
down_revision = "0050_bike_spatial_v0536"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.37', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.36', updated_at=now() WHERE key='schema_version'"))
