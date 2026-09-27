"""Bicycle context trail + two-wheel rescue signature V0.5.35.

Revision ID: 0049_two_wheel_sig_v0535
Revises: 0048_two_wheel_gate_v0534
"""
from alembic import op
import sqlalchemy as sa

revision = "0049_two_wheel_sig_v0535"
down_revision = "0048_two_wheel_gate_v0534"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.35', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.34', updated_at=now() WHERE key='schema_version'"))
