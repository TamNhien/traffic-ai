"""Dataset and fine-tune studio V0.5.0.

Revision ID: 0014_dataset_training_v50
Revises: 0013_smooth_playback_v41
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_dataset_training_v50"
down_revision = "0013_smooth_playback_v41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("source_camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("root_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("sample_every_n_frames", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("image_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("labeled_images", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("box_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("train_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("val_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("test_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("classes_json", sa.Text(), nullable=False, server_default='["motorcycle","bicycle","car","bus","truck"]'),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_datasets_slug"),
    )
    op.create_index("ix_datasets_slug", "datasets", ["slug"])
    op.create_index("ix_datasets_status", "datasets", ["status"])
    op.create_index("ix_datasets_source_camera_id", "datasets", ["source_camera_id"])

    op.create_table(
        "training_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_id", sa.Integer(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_model", sa.String(length=160), nullable=False, server_default="yolo26s.pt"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("epochs", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("imgsz", sa.Integer(), nullable=False, server_default="640"),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("device", sa.String(length=40), nullable=False, server_default="auto"),
        sa.Column("current_epoch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("precision", sa.Float(), nullable=True),
        sa.Column("recall", sa.Float(), nullable=True),
        sa.Column("map50", sa.Float(), nullable=True),
        sa.Column("map50_95", sa.Float(), nullable=True),
        sa.Column("best_model_path", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_training_runs_dataset_id", "training_runs", ["dataset_id"])
    op.create_index("ix_training_runs_status", "training_runs", ["status"])
    op.execute(sa.text("UPDATE system_settings SET value='0.5.0', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.drop_index("ix_training_runs_status", table_name="training_runs")
    op.drop_index("ix_training_runs_dataset_id", table_name="training_runs")
    op.drop_table("training_runs")
    op.drop_index("ix_datasets_source_camera_id", table_name="datasets")
    op.drop_index("ix_datasets_status", table_name="datasets")
    op.drop_index("ix_datasets_slug", table_name="datasets")
    op.drop_table("datasets")
    op.execute(sa.text("UPDATE system_settings SET value='0.4.1', updated_at=now() WHERE key='schema_version'"))
