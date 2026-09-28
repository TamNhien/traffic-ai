"""Precision Closure 9.2 + passage-cycle state V0.5.46.

Revision ID: 0060_precision_closure_v0546
Revises: 0059_fp_closure_v0545
"""
from alembic import op
import sqlalchemy as sa

revision = "0060_precision_closure_v0546"
down_revision = "0059_fp_closure_v0545"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.46', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.45', updated_at=now() WHERE key='schema_version'"))
