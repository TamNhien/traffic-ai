"""Realtime Gate 4.0 model/defaults marker.

Revision ID: 0012_realtime_gate_v4
Revises: 0011_gateway_dns_runtime
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_realtime_gate_v4"
down_revision = "0011_gateway_dns_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep the older YOLO26n pretrained row for experiments. Only move the
    # active baseline to YOLO26s when the user has not already activated a
    # custom/fine-tuned model such as best.pt.
    op.execute(sa.text("""
        INSERT INTO ai_models (name, version, architecture, model_path, training_dataset, is_active)
        SELECT 'YOLO26s COCO', 'pretrained', 'YOLO26', 'yolo26s.pt', 'COCO', false
        WHERE NOT EXISTS (
            SELECT 1 FROM ai_models WHERE name='YOLO26s COCO' AND version='pretrained'
        )
    """))
    op.execute(sa.text("""
        UPDATE ai_models
           SET architecture='YOLO26', model_path='yolo26s.pt', training_dataset='COCO'
         WHERE name='YOLO26s COCO' AND version='pretrained'
    """))
    op.execute(sa.text("""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM ai_models WHERE is_active=true AND version <> 'pretrained') THEN
            UPDATE ai_models SET is_active=false WHERE is_active=true;
            UPDATE ai_models SET is_active=true WHERE name='YOLO26s COCO' AND version='pretrained';
          END IF;
        END $$
    """))
    # Lower only untouched defaults from V0.3.1. User-tuned values are preserved.
    op.execute(sa.text("UPDATE cameras SET confidence_threshold=0.18 WHERE ABS(confidence_threshold - 0.20) < 0.000001"))
    op.execute(sa.text("UPDATE system_settings SET value='0.4.0', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE ai_models SET is_active=false WHERE name='YOLO26s COCO' AND version='pretrained'"))
    op.execute(sa.text("UPDATE ai_models SET is_active=true WHERE name='YOLO26n COCO' AND version='pretrained'"))
    op.execute(sa.text("UPDATE system_settings SET value='0.3.3', updated_at=now() WHERE key='schema_version'"))
