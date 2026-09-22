"""Repair local schema drift and record runtime-stability release.

Revision ID: 0004_runtime_stability
Revises: 0003_yolo26_baseline
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_runtime_stability"
down_revision: Union[str, None] = "0003_yolo26_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Repair idempotent các cột cần cho pipeline nếu database local từng bị lệch schema.
    op.execute(sa.text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS confidence_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.35"))
    op.execute(sa.text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS line_x1 DOUBLE PRECISION NOT NULL DEFAULT 0.1"))
    op.execute(sa.text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS line_y1 DOUBLE PRECISION NOT NULL DEFAULT 0.5"))
    op.execute(sa.text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS line_x2 DOUBLE PRECISION NOT NULL DEFAULT 0.9"))
    op.execute(sa.text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS line_y2 DOUBLE PRECISION NOT NULL DEFAULT 0.5"))

    # Bảo đảm baseline YOLO26 tồn tại. Không ghi đè model tùy chỉnh đang active.
    op.execute(
        sa.text(
            """
            INSERT INTO ai_models (name, version, architecture, model_path, training_dataset, is_active)
            SELECT 'YOLO26n COCO', 'pretrained', 'YOLO26', 'yolo26n.pt', 'COCO', false
            WHERE NOT EXISTS (
                SELECT 1 FROM ai_models WHERE name='YOLO26n COCO' AND version='pretrained'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE ai_models
               SET is_active=false
             WHERE name='YOLO11n COCO' AND version='pretrained' AND is_active=true
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE ai_models
               SET is_active=true, architecture='YOLO26', model_path='yolo26n.pt', training_dataset='COCO'
             WHERE name='YOLO26n COCO' AND version='pretrained'
               AND NOT EXISTS (SELECT 1 FROM ai_models WHERE is_active=true)
            """
        )
    )
    op.execute(sa.text("UPDATE system_settings SET value='0.2.3', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.2.1', updated_at=now() WHERE key='schema_version'"))
