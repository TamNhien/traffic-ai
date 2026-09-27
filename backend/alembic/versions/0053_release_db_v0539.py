"""Release EOL hygiene + PostgreSQL client guard V0.5.39.

Revision ID: 0053_release_db_v0539
Revises: 0052_bike_ultra_v0538
"""
from alembic import op
import sqlalchemy as sa

revision = "0053_release_db_v0539"
down_revision = "0052_bike_ultra_v0538"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.39', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.38', updated_at=now() WHERE key='schema_version'"))
