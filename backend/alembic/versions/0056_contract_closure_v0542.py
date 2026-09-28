"""Full-source contract closure + compact telemetry compatibility V0.5.42.

Revision ID: 0056_contract_closure_v0542
Revises: 0055_span_recovery_v0541
"""
from alembic import op
import sqlalchemy as sa

revision = "0056_contract_closure_v0542"
down_revision = "0055_span_recovery_v0541"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.42', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.41', updated_at=now() WHERE key='schema_version'"))
