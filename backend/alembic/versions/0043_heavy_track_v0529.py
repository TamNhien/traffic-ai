"""Heavy Track Fusion + Center-Gate Rescue V0.5.29.

Revision ID: 0043_heavy_track_v0529
Revises: 0042_origin_heavy_v0528
"""
from alembic import op
import sqlalchemy as sa

revision = "0043_heavy_track_v0529"
down_revision = "0042_origin_heavy_v0528"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.29', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.28', updated_at=now() WHERE key='schema_version'"))
