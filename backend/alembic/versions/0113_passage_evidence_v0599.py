"""Read-only verified passage evidence worklist V0.5.99.

No GT/events or counting schema is modified; version metadata only.
"""
from alembic import op
import sqlalchemy as sa

revision = "0113_passage_evidence_v0599"
down_revision = "0112_clock_owner_v0598"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.99', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.98', updated_at=now() WHERE key='schema_version'"))
