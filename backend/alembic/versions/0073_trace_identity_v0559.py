"""Trace Identity and Delivery Completion V0.5.59.

Revision ID: 0073_trace_identity_v0559
Revises: 0072_trace_lifecycle_v0558
"""
from alembic import op
import sqlalchemy as sa

revision = "0073_trace_identity_v0559"
down_revision = "0072_trace_lifecycle_v0558"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.59', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.58', updated_at=now() WHERE key='schema_version'"))
