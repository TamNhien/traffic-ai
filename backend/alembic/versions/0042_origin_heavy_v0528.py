"""Video-Origin + Heavy-Vehicle Gate Rescue V0.5.28.

Revision ID: 0042_origin_heavy_v0528
Revises: 0041_dual_refiner_v0527
"""
from alembic import op
import sqlalchemy as sa

revision = "0042_origin_heavy_v0528"
down_revision = "0041_dual_refiner_v0527"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.28', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.27', updated_at=now() WHERE key='schema_version'"))
