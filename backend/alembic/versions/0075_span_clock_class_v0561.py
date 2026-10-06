"""Span clock reconciliation and fresh class closure V0.5.61.

Revision ID: 0075_span_clock_class_v0561
Revises: 0074_stop_ack_compat_v0560
"""
from alembic import op
import sqlalchemy as sa

revision = "0075_span_clock_class_v0561"
down_revision = "0074_stop_ack_compat_v0560"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.61', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.60', updated_at=now() WHERE key='schema_version'"))
