"""Balanced Recall Recovery 9.3 V0.5.47.

Revision ID: 0061_balanced_recall_v0547
Revises: 0060_precision_closure_v0546
"""
from alembic import op
import sqlalchemy as sa

revision = "0061_balanced_recall_v0547"
down_revision = "0060_precision_closure_v0546"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.47', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.46', updated_at=now() WHERE key='schema_version'"))
