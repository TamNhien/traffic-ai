"""Gate class prescan and backend delivery evidence V0.5.63.

Revision ID: 0077_delivery_prescan_v0563
Revises: 0076_identity_audit_v0562
"""
from alembic import op
import sqlalchemy as sa

revision = "0077_delivery_prescan_v0563"
down_revision = "0076_identity_audit_v0562"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.63', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.62', updated_at=now() WHERE key='schema_version'"))
