"""Benchmark Integrity + Crossing Engine 7.1 V0.5.23.

Revision ID: 0037_integrity_v0523
Revises: 0036_gt_reuse_v0522
"""
from alembic import op
import sqlalchemy as sa

revision = "0037_integrity_v0523"
down_revision = "0036_gt_reuse_v0522"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("counting_sessions", sa.Column("worker_total_vehicles", sa.Integer(), nullable=True))
    op.add_column("counting_sessions", sa.Column("dedup_suppressed_events", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("counting_sessions", sa.Column("human_guard_rejections", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("vehicle_events", sa.Column("crossing_x", sa.Float(), nullable=True))
    op.add_column("vehicle_events", sa.Column("crossing_y", sa.Float(), nullable=True))

    # Preserve the pre-V0.5.23 worker-facing total, then make total_vehicles mean
    # exactly what Benchmark sees: persisted VehicleEvent rows. This repairs the
    # historical Session #120 style mismatch (worker 162 vs DB/timed 158).
    op.execute(sa.text("UPDATE counting_sessions SET worker_total_vehicles = total_vehicles WHERE worker_total_vehicles IS NULL"))
    op.execute(sa.text("""
        UPDATE counting_sessions AS s
        SET total_vehicles = (
            SELECT COUNT(*) FROM vehicle_events AS e WHERE e.session_id = s.id
        )
        WHERE EXISTS (SELECT 1 FROM vehicle_events AS e2 WHERE e2.session_id = s.id)
    """))
    op.execute(sa.text("""
        UPDATE counting_sessions
        SET dedup_suppressed_events = GREATEST(COALESCE(worker_total_vehicles, 0) - total_vehicles, 0)
    """))
    op.execute(sa.text("UPDATE system_settings SET value='0.5.23', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.drop_column("vehicle_events", "crossing_y")
    op.drop_column("vehicle_events", "crossing_x")
    op.drop_column("counting_sessions", "human_guard_rejections")
    op.drop_column("counting_sessions", "dedup_suppressed_events")
    op.drop_column("counting_sessions", "worker_total_vehicles")
    op.execute(sa.text("UPDATE system_settings SET value='0.5.22', updated_at=now() WHERE key='schema_version'"))
