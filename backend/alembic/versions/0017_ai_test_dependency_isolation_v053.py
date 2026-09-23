"""AI test dependency isolation V0.5.3.

Revision ID: 0017_ai_test_dep_v053
Revises: 0016_contract_alignment_v052
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_ai_test_dep_v053"
down_revision = "0016_contract_alignment_v052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.3', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.2', updated_at=now() WHERE key='schema_version'"))
