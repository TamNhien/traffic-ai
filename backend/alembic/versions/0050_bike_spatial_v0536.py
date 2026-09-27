"""Weak-motor bicycle context + spatial benchmark audit V0.5.36.

Revision ID: 0050_bike_spatial_v0536
Revises: 0049_two_wheel_sig_v0535
"""
from alembic import op
import sqlalchemy as sa

revision = "0050_bike_spatial_v0536"
down_revision = "0049_two_wheel_sig_v0535"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.36', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.35', updated_at=now() WHERE key='schema_version'"))
