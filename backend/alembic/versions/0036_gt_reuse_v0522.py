"""Ground Truth reuse UX V0.5.22.

Revision ID: 0036_gt_reuse_v0522
Revises: 0035_crossing_v0521
"""
from alembic import op
import sqlalchemy as sa

revision = "0036_gt_reuse_v0522"
down_revision = "0035_crossing_v0521"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.22', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.21', updated_at=now() WHERE key='schema_version'"))
