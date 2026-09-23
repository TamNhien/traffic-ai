"""Alembic revision-length hardening V0.5.4.

Revision ID: 0018_alembic_guard_v054
Revises: 0017_ai_test_dep_v053
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_alembic_guard_v054"
down_revision = "0017_ai_test_dep_v053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Alembic creates version_num as VARCHAR(32) by default. Widen it so
        # future descriptive revision IDs cannot break startup.
        op.execute(sa.text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"))
    op.execute(sa.text("UPDATE system_settings SET value='0.5.4', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    # Keep the wider Alembic column on downgrade; shrinking can truncate a
    # revision value and is not required for application rollback.
    op.execute(sa.text("UPDATE system_settings SET value='0.5.3', updated_at=now() WHERE key='schema_version'"))
