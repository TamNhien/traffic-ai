"""Domain-supported demotion of held truck semantics V0.5.65.

Revision ID: 0079_van_semantics_v0565
Revises: 0078_replay_audit_v0564
"""
from alembic import op
import sqlalchemy as sa

revision = "0079_van_semantics_v0565"
down_revision = "0078_replay_audit_v0564"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.65', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.64', updated_at=now() WHERE key='schema_version'"))
