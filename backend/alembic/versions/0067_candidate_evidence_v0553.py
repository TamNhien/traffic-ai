"""Candidate Eligibility + Passage Evidence V0.5.53.

Revision ID: 0067_candidate_evidence_v0553
Revises: 0066_observed_path_v0552
"""
from alembic import op
import sqlalchemy as sa

revision = "0067_candidate_evidence_v0553"
down_revision = "0066_observed_path_v0552"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.53', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.52', updated_at=now() WHERE key='schema_version'"))
