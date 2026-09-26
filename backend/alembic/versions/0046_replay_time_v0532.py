"""Deterministic replay + confidence-aware time sync V0.5.32.

Revision ID: 0046_replay_time_v0532
Revises: 0045_cross_time_v0531
"""
from alembic import op
import sqlalchemy as sa

revision = "0046_replay_time_v0532"
down_revision = "0045_cross_time_v0531"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.32', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.31', updated_at=now() WHERE key='schema_version'"))
