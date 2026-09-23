"""Integrated annotation studio V0.5.6.

Revision ID: 0020_annotation_studio_v056
Revises: 0019_activation_ui_v055
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_annotation_studio_v056"
down_revision = "0019_activation_ui_v055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("reviewed_images", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("datasets", sa.Column("difficult_images", sa.Integer(), nullable=False, server_default="0"))
    op.execute(sa.text("UPDATE system_settings SET value='0.5.6', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.drop_column("datasets", "difficult_images")
    op.drop_column("datasets", "reviewed_images")
    op.execute(sa.text("UPDATE system_settings SET value='0.5.5', updated_at=now() WHERE key='schema_version'"))
