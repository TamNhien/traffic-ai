"""Test-contract alignment V0.5.2.

Revision ID: 0016_contract_alignment_v052
Revises: 0015_ui_test_hardening_v051
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_contract_alignment_v052"
down_revision = "0015_ui_test_hardening_v051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.2', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.1', updated_at=now() WHERE key='schema_version'"))
