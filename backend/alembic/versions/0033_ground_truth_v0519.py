"""Ground-truth Counting Benchmark V0.5.19.

Revision ID: 0033_ground_truth_v0519
Revises: 0032_crossing_engine_v0518
"""
from alembic import op
import sqlalchemy as sa

revision = "0033_ground_truth_v0519"
down_revision = "0032_crossing_engine_v0518"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("counting_sessions", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("counting_sessions", sa.Column("source_fps", sa.Float(), nullable=True))
    op.add_column("counting_sessions", sa.Column("source_duration_seconds", sa.Float(), nullable=True))

    op.add_column("vehicle_events", sa.Column("source_frame_index", sa.Integer(), nullable=True))
    op.add_column("vehicle_events", sa.Column("source_time_seconds", sa.Float(), nullable=True))
    op.add_column("vehicle_events", sa.Column("crossing_method", sa.String(length=24), nullable=True))
    op.create_index("ix_vehicle_events_source_frame_index", "vehicle_events", ["source_frame_index"])
    op.create_index("ix_vehicle_events_source_time_seconds", "vehicle_events", ["source_time_seconds"])

    op.create_table(
        "counting_benchmarks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("counting_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_fps", sa.Float(), nullable=True),
        sa.Column("source_duration_seconds", sa.Float(), nullable=True),
        sa.Column("tolerance_seconds", sa.Float(), nullable=False, server_default="0.75"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_counting_benchmarks_camera_id", "counting_benchmarks", ["camera_id"])
    op.create_index("ix_counting_benchmarks_session_id", "counting_benchmarks", ["session_id"])

    op.create_table(
        "ground_truth_crossings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("benchmark_id", sa.Integer(), sa.ForeignKey("counting_benchmarks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_time_seconds", sa.Float(), nullable=False),
        sa.Column("source_frame_index", sa.Integer(), nullable=True),
        sa.Column("vehicle_type", sa.String(length=24), nullable=False, server_default="motorcycle"),
        sa.Column("direction", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ground_truth_crossings_benchmark_id", "ground_truth_crossings", ["benchmark_id"])
    op.create_index("ix_ground_truth_crossings_source_time_seconds", "ground_truth_crossings", ["source_time_seconds"])

    op.execute(sa.text("UPDATE system_settings SET value='0.5.19', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.drop_index("ix_ground_truth_crossings_source_time_seconds", table_name="ground_truth_crossings")
    op.drop_index("ix_ground_truth_crossings_benchmark_id", table_name="ground_truth_crossings")
    op.drop_table("ground_truth_crossings")
    op.drop_index("ix_counting_benchmarks_session_id", table_name="counting_benchmarks")
    op.drop_index("ix_counting_benchmarks_camera_id", table_name="counting_benchmarks")
    op.drop_table("counting_benchmarks")
    op.drop_index("ix_vehicle_events_source_time_seconds", table_name="vehicle_events")
    op.drop_index("ix_vehicle_events_source_frame_index", table_name="vehicle_events")
    op.drop_column("vehicle_events", "crossing_method")
    op.drop_column("vehicle_events", "source_time_seconds")
    op.drop_column("vehicle_events", "source_frame_index")
    op.drop_column("counting_sessions", "source_duration_seconds")
    op.drop_column("counting_sessions", "source_fps")
    op.drop_column("counting_sessions", "source_url")
    op.execute(sa.text("UPDATE system_settings SET value='0.5.18', updated_at=now() WHERE key='schema_version'"))
