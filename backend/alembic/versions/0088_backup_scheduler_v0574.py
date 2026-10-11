"""V0.5.74: bump schema version for backup/restore service release.
Backup catalogs live outside PostgreSQL in an isolated Docker volume.
"""
from alembic import op
import sqlalchemy as sa

revision = "0088_backup_scheduler_v0574"
down_revision = "0087_unicode_usernames_v0573"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.74', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.73', updated_at=now() WHERE key='schema_version'"))
