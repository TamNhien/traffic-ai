"""Observed Path + Clean Frame + Release Automation V0.5.52.

Revision ID: 0066_observed_path_v0552
Revises: 0065_span_shadow_v0551
"""
from alembic import op
import sqlalchemy as sa

revision = "0066_observed_path_v0552"
down_revision = "0065_span_shadow_v0551"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.52', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.51', updated_at=now() WHERE key='schema_version'"))
