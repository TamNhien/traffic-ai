"""Road Guard 2.0 + release hygiene V0.5.12.

Revision ID: 0026_road_guard_v0512
Revises: 0025_road_zone_v0511
"""
from alembic import op
import sqlalchemy as sa

revision = "0026_road_guard_v0512"
down_revision = "0025_road_zone_v0511"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Align untouched legacy/default gates with the Road Zone-safe frontend
    # preset. Custom user gates are intentionally left unchanged.
    op.execute(sa.text("""
        UPDATE cameras
        SET line_x1 = 0.32, line_y1 = 0.59, line_x2 = 0.84, line_y2 = 0.59
        WHERE abs(line_x1 - 0.10) < 0.000001
          AND abs(line_y1 - 0.50) < 0.000001
          AND abs(line_x2 - 0.90) < 0.000001
          AND abs(line_y2 - 0.50) < 0.000001
    """))
    op.execute(sa.text("ALTER TABLE cameras ALTER COLUMN line_x1 SET DEFAULT 0.32"))
    op.execute(sa.text("ALTER TABLE cameras ALTER COLUMN line_y1 SET DEFAULT 0.59"))
    op.execute(sa.text("ALTER TABLE cameras ALTER COLUMN line_x2 SET DEFAULT 0.84"))
    op.execute(sa.text("ALTER TABLE cameras ALTER COLUMN line_y2 SET DEFAULT 0.59"))
    op.execute(sa.text("UPDATE system_settings SET value='0.5.12', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE cameras ALTER COLUMN line_x1 SET DEFAULT 0.10"))
    op.execute(sa.text("ALTER TABLE cameras ALTER COLUMN line_y1 SET DEFAULT 0.50"))
    op.execute(sa.text("ALTER TABLE cameras ALTER COLUMN line_x2 SET DEFAULT 0.90"))
    op.execute(sa.text("ALTER TABLE cameras ALTER COLUMN line_y2 SET DEFAULT 0.50"))
    op.execute(sa.text("UPDATE system_settings SET value='0.5.11', updated_at=now() WHERE key='schema_version'"))
