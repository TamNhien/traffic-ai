"""Refinement Admission and Passage Lifecycle V0.5.55.

Revision ID: 0069_refine_admission_v0555
Revises: 0068_gate_semantics_v0554
"""
from alembic import op
import sqlalchemy as sa

revision = "0069_refine_admission_v0555"
down_revision = "0068_gate_semantics_v0554"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.55', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.54', updated_at=now() WHERE key='schema_version'"))
