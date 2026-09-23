"""Road-zone counting V0.5.11.

Revision ID: 0025_road_zone_v0511
Revises: 0024_ci_node_v0510
"""
from alembic import op
import sqlalchemy as sa

revision = "0025_road_zone_v0511"
down_revision = "0024_ci_node_v0510"
branch_labels = None
depends_on = None


def upgrade() -> None:
    defaults = {
        "road_x1": "0.20", "road_y1": "0.16", "road_x2": "0.80", "road_y2": "0.16",
        "road_x3": "0.96", "road_y3": "0.98", "road_x4": "0.04", "road_y4": "0.98",
    }
    for name, default in defaults.items():
        op.add_column("cameras", sa.Column(name, sa.Float(), nullable=False, server_default=default))
    op.execute(sa.text("UPDATE system_settings SET value='0.5.11', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    for name in ("road_y4", "road_x4", "road_y3", "road_x3", "road_y2", "road_x2", "road_y1", "road_x1"):
        op.drop_column("cameras", name)
    op.execute(sa.text("UPDATE system_settings SET value='0.5.10', updated_at=now() WHERE key='schema_version'"))
