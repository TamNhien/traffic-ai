"""Benchmark gate overlay snapshot V0.5.20.

Revision ID: 0034_benchmark_overlay_v0520
Revises: 0033_ground_truth_v0519
"""
from alembic import op
import sqlalchemy as sa

revision = "0034_benchmark_overlay_v0520"
down_revision = "0033_ground_truth_v0519"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = [
        ("line_x1", "0.32"), ("line_y1", "0.59"),
        ("line_x2", "0.84"), ("line_y2", "0.59"),
        ("road_x1", "0.20"), ("road_y1", "0.16"),
        ("road_x2", "0.80"), ("road_y2", "0.16"),
        ("road_x3", "0.96"), ("road_y3", "0.98"),
        ("road_x4", "0.04"), ("road_y4", "0.98"),
    ]
    for name, default in columns:
        op.add_column(
            "counting_benchmarks",
            sa.Column(name, sa.Float(), nullable=False, server_default=default),
        )

    # Existing V0.5.19 benchmarks did not persist gate geometry. Backfill them
    # from their camera's current geometry so they become usable immediately.
    op.execute(sa.text("""
        UPDATE counting_benchmarks AS b
        SET line_x1 = c.line_x1,
            line_y1 = c.line_y1,
            line_x2 = c.line_x2,
            line_y2 = c.line_y2,
            road_x1 = c.road_x1,
            road_y1 = c.road_y1,
            road_x2 = c.road_x2,
            road_y2 = c.road_y2,
            road_x3 = c.road_x3,
            road_y3 = c.road_y3,
            road_x4 = c.road_x4,
            road_y4 = c.road_y4
        FROM cameras AS c
        WHERE b.camera_id = c.id
    """))

    op.execute(sa.text("UPDATE system_settings SET value='0.5.20', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    for name in [
        "road_y4", "road_x4", "road_y3", "road_x3",
        "road_y2", "road_x2", "road_y1", "road_x1",
        "line_y2", "line_x2", "line_y1", "line_x1",
    ]:
        op.drop_column("counting_benchmarks", name)
    op.execute(sa.text("UPDATE system_settings SET value='0.5.19', updated_at=now() WHERE key='schema_version'"))
