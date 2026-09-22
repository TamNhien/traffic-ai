"""Switch the default pretrained baseline from YOLO11n to YOLO26n.

Revision ID: 0003_yolo26_baseline
Revises: 0002_ai_pipeline
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_yolo26_baseline"
down_revision: Union[str, None] = "0002_ai_pipeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Giữ baseline cũ để so sánh thực nghiệm nhưng chuyển mặc định sang YOLO26n.
    op.execute(sa.text("UPDATE ai_models SET is_active=false WHERE is_active=true"))
    op.execute(
        sa.text(
            """
            INSERT INTO ai_models (name, version, architecture, model_path, training_dataset, is_active)
            SELECT 'YOLO26n COCO', 'pretrained', 'YOLO26', 'yolo26n.pt', 'COCO', true
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
               SET architecture='YOLO26', model_path='yolo26n.pt', training_dataset='COCO', is_active=true
             WHERE name='YOLO26n COCO' AND version='pretrained'
            """
        )
    )
    op.execute(sa.text("UPDATE system_settings SET value='0.2.1', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE ai_models SET is_active=false WHERE name='YOLO26n COCO' AND version='pretrained'"))
    op.execute(sa.text("UPDATE ai_models SET is_active=true WHERE name='YOLO11n COCO' AND version='pretrained'"))
    op.execute(sa.text("UPDATE system_settings SET value='0.2.0', updated_at=now() WHERE key='schema_version'"))
