"""Add AI pipeline camera configuration and baseline model.

Revision ID: 0002_ai_pipeline
Revises: 0001_initial_schema
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_ai_pipeline"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Dùng IF NOT EXISTS để chịu được database local từng bị dừng giữa quá trình
    # nâng cấp hoặc đã được bổ sung cột thủ công trong quá trình phát triển.
    op.execute(sa.text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS confidence_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.35"))
    op.execute(sa.text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS line_x1 DOUBLE PRECISION NOT NULL DEFAULT 0.1"))
    op.execute(sa.text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS line_y1 DOUBLE PRECISION NOT NULL DEFAULT 0.5"))
    op.execute(sa.text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS line_x2 DOUBLE PRECISION NOT NULL DEFAULT 0.9"))
    op.execute(sa.text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS line_y2 DOUBLE PRECISION NOT NULL DEFAULT 0.5"))

    # Không phụ thuộc tên constraint. Một số database local cũ có thể mang tên
    # constraint/index khác dù cặp (name, version) vẫn là duy nhất.
    op.execute(
        sa.text(
            """
            INSERT INTO ai_models (name, version, architecture, model_path, training_dataset, is_active)
            SELECT 'YOLO11n COCO', 'pretrained', 'YOLO11', 'yolo11n.pt', 'COCO', true
            WHERE NOT EXISTS (
                SELECT 1 FROM ai_models WHERE name='YOLO11n COCO' AND version='pretrained'
            )
            """
        )
    )
    op.execute(sa.text("UPDATE system_settings SET value='0.2.0', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.1.0', updated_at=now() WHERE key='schema_version'"))
    op.execute(sa.text("DELETE FROM ai_models WHERE name='YOLO11n COCO' AND version='pretrained'"))
    op.drop_column("cameras", "line_y2")
    op.drop_column("cameras", "line_x2")
    op.drop_column("cameras", "line_y1")
    op.drop_column("cameras", "line_x1")
    op.drop_column("cameras", "confidence_threshold")
