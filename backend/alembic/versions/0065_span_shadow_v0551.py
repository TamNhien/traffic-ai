"""Verified Span + Event Ordering Closure 9.7 V0.5.51.

Revision ID: 0065_span_shadow_v0551
Revises: 0064_geometry_semantic_v0550
"""
from alembic import op
import sqlalchemy as sa

revision = "0065_span_shadow_v0551"
down_revision = "0064_geometry_semantic_v0550"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.51', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.50', updated_at=now() WHERE key='schema_version'"))
