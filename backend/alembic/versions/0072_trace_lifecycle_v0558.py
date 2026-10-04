"""Trace Lifecycle and Source Evidence V0.5.58.

Revision ID: 0072_trace_lifecycle_v0558
Revises: 0071_anchor_lifecycle_v0557
"""
from alembic import op
import sqlalchemy as sa

revision = "0072_trace_lifecycle_v0558"
down_revision = "0071_anchor_lifecycle_v0557"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.58', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.57', updated_at=now() WHERE key='schema_version'"))
