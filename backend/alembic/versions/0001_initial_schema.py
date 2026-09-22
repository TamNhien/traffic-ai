"""Initial Traffic AI schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

camera_status = sa.Enum("active", "inactive", "error", name="camera_status")
source_type = sa.Enum("rtsp", "video", "webcam", name="source_type")
vehicle_type = sa.Enum("motorcycle", "bicycle", "car", "bus", "truck", "other", name="vehicle_type")
vehicle_direction = sa.Enum("in", "out", "unknown", name="vehicle_direction")
session_status = sa.Enum("running", "completed", "stopped", "error", name="session_status")
vehicle_count_type = sa.Enum("motorcycle", "bicycle", "car", "bus", "truck", "other", name="vehicle_count_type")
vehicle_count_direction = sa.Enum("in", "out", "unknown", name="vehicle_count_direction")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=160)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=255)),
        sa.Column("description", sa.Text()),
        sa.Column("status", camera_status, nullable=False, server_default="inactive"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_cameras_code", "cameras", ["code"], unique=True)

    op.create_table(
        "ai_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("architecture", sa.String(length=80), nullable=False),
        sa.Column("model_path", sa.Text(), nullable=False),
        sa.Column("training_dataset", sa.String(length=255)),
        sa.Column("precision", sa.Float()),
        sa.Column("recall", sa.Float()),
        sa.Column("map50", sa.Float()),
        sa.Column("map50_95", sa.Float()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", "version", name="uq_ai_model_name_version"),
    )

    op.create_table(
        "counting_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("ai_models.id", ondelete="SET NULL")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("status", session_status, nullable=False, server_default="running"),
        sa.Column("total_vehicles", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_fps", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_counting_sessions_camera_id", "counting_sessions", ["camera_id"])
    op.create_index("ix_counting_sessions_model_id", "counting_sessions", ["model_id"])

    op.create_table(
        "vehicle_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("counting_sessions.id", ondelete="SET NULL")),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("ai_models.id", ondelete="SET NULL")),
        sa.Column("tracking_id", sa.Integer()),
        sa.Column("vehicle_type", vehicle_type, nullable=False),
        sa.Column("direction", vehicle_direction, nullable=False, server_default="unknown"),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("snapshot_path", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ["camera_id", "session_id", "model_id", "tracking_id", "vehicle_type", "direction", "detected_at"]:
        op.create_index(f"ix_vehicle_events_{column}", "vehicle_events", [column])

    op.create_table(
        "vehicle_counts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_type", vehicle_count_type, nullable=False),
        sa.Column("direction", vehicle_count_direction, nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ["camera_id", "vehicle_type", "direction", "period_start"]:
        op.create_index(f"ix_vehicle_counts_{column}", "vehicle_counts", [column])

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)

    op.execute(
        sa.text(
            """
            INSERT INTO system_settings (key, value, description)
            VALUES
              ('schema_version', '0.1.0', 'Traffic AI database schema version'),
              ('counting_timezone', 'Asia/Ho_Chi_Minh', 'Default statistics timezone')
            ON CONFLICT (key) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_table("vehicle_counts")
    op.drop_table("vehicle_events")
    op.drop_table("counting_sessions")
    op.drop_table("ai_models")
    op.drop_table("cameras")
    op.drop_table("users")

    bind = op.get_bind()
    vehicle_count_direction.drop(bind, checkfirst=True)
    vehicle_count_type.drop(bind, checkfirst=True)
    session_status.drop(bind, checkfirst=True)
    vehicle_direction.drop(bind, checkfirst=True)
    vehicle_type.drop(bind, checkfirst=True)
    source_type.drop(bind, checkfirst=True)
    camera_status.drop(bind, checkfirst=True)
