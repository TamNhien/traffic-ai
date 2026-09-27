"""Bicycle precision + GT class audit V0.5.33.

Revision ID: 0047_two_wheel_v0533
Revises: 0046_replay_time_v0532
"""
from alembic import op
import sqlalchemy as sa

revision = "0047_two_wheel_v0533"
down_revision = "0046_replay_time_v0532"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.33', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.32', updated_at=now() WHERE key='schema_version'"))
