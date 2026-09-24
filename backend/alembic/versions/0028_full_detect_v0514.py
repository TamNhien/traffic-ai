"""Full-frame detection + strict road counting V0.5.14.

Revision ID: 0028_full_detect_v0514
Revises: 0027_fast_overlay_v0513
"""
from alembic import op
import sqlalchemy as sa

revision = "0028_full_detect_v0514"
down_revision = "0027_fast_overlay_v0513"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.14', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.13', updated_at=now() WHERE key='schema_version'"))
