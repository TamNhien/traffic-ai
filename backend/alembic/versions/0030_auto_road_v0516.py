"""Auto Road-Zone calibration V0.5.16.

Revision ID: 0030_auto_road_v0516
Revises: 0029_hybrid_recall_v0515
"""
from alembic import op
import sqlalchemy as sa

revision = "0030_auto_road_v0516"
down_revision = "0029_hybrid_recall_v0515"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.16', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.15', updated_at=now() WHERE key='schema_version'"))
