"""Release hygiene and V0.2.9 marker.

Revision ID: 0007_release_hygiene
Revises: 0006_source_management
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_release_hygiene"
down_revision = "0006_source_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.2.9', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.2.8', updated_at=now() WHERE key='schema_version'"))
