"""Gate Corridor + Semantic Evidence V0.5.54.

Revision ID: 0068_gate_semantics_v0554
Revises: 0067_candidate_evidence_v0553
"""
from alembic import op
import sqlalchemy as sa

revision = "0068_gate_semantics_v0554"
down_revision = "0067_candidate_evidence_v0553"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.54', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.53', updated_at=now() WHERE key='schema_version'"))
