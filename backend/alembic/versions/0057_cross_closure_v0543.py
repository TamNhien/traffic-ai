"""Crossing Closure 8.6 + passage re-arm V0.5.43.

Revision ID: 0057_cross_closure_v0543
Revises: 0056_contract_closure_v0542
"""
from alembic import op
import sqlalchemy as sa

revision = "0057_cross_closure_v0543"
down_revision = "0056_contract_closure_v0542"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.43', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.42', updated_at=now() WHERE key='schema_version'"))
