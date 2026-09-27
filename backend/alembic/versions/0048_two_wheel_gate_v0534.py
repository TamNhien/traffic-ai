"""Two-wheel context + center-gate rescue V0.5.34.

Revision ID: 0048_two_wheel_gate_v0534
Revises: 0047_two_wheel_v0533
"""
from alembic import op
import sqlalchemy as sa

revision = "0048_two_wheel_gate_v0534"
down_revision = "0047_two_wheel_v0533"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.34', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.33', updated_at=now() WHERE key='schema_version'"))
