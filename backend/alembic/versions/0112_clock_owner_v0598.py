"""Passage-owned clock hints V0.5.98."""
from alembic import op
import sqlalchemy as sa

revision = "0112_clock_owner_v0598"
down_revision = "0111_count_review_v0597"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.98', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.97', updated_at=now() WHERE key='schema_version'"))
