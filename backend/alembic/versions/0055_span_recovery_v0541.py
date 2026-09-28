"""Verified Anchor-Span Recovery + Post-Confirm Closure + Cross-Frame Bicycle Decision Audit 8.5.

Revision ID: 0055_span_recovery_v0541
Revises: 0054_bike_gate_v0540
"""
from alembic import op
import sqlalchemy as sa

revision = "0055_span_recovery_v0541"
down_revision = "0054_bike_gate_v0540"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.41', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.40', updated_at=now() WHERE key='schema_version'"))
