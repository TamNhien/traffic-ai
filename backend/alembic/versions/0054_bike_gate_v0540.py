"""Cross-Frame Bicycle Context + Gate-Span Benchmark Audit 8.4.

Revision ID: 0054_bike_gate_v0540
Revises: 0053_release_db_v0539
"""
from alembic import op
import sqlalchemy as sa

revision = "0054_bike_gate_v0540"
down_revision = "0053_release_db_v0539"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.40', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.39', updated_at=now() WHERE key='schema_version'"))
