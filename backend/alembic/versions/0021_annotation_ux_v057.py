"""Annotation Studio UX clarity V0.5.7.

Revision ID: 0021_annotation_ux_v057
Revises: 0020_annotation_studio_v056
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_annotation_ux_v057"
down_revision = "0020_annotation_studio_v056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.7', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.6', updated_at=now() WHERE key='schema_version'"))
