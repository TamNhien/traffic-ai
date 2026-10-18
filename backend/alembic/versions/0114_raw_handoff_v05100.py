"""Verified same raw token handoff guard V0.5.100, metadata only.

The counter retains all saved historic events. No benchmark scoring/GT mutation.
"""
from alembic import op
import sqlalchemy as sa

revision = "0114_raw_handoff_v05100"
down_revision = "0113_passage_evidence_v0599"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.100', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.99', updated_at=now() WHERE key='schema_version'"))
