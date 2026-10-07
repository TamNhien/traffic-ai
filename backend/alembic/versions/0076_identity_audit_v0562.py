"""Identity separation and trace provenance V0.5.62.

Revision ID: 0076_identity_audit_v0562
Revises: 0075_span_clock_class_v0561
"""
from alembic import op
import sqlalchemy as sa

revision = "0076_identity_audit_v0562"
down_revision = "0075_span_clock_class_v0561"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.62', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.61', updated_at=now() WHERE key='schema_version'"))
