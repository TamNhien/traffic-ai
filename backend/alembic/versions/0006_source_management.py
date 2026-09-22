"""Camera/video source management and V0.2.8 marker.

Revision ID: 0006_source_management
Revises: 0005_counting_reliability
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_source_management"
down_revision = "0005_counting_reliability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.2.8', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.2.7', updated_at=now() WHERE key='schema_version'"))
