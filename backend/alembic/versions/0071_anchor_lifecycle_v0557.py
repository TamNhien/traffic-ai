"""Anchor Lifecycle and Evidence Provenance V0.5.57.

Revision ID: 0071_anchor_lifecycle_v0557
Revises: 0070_benchmark_evidence_v0556
"""
from alembic import op
import sqlalchemy as sa

revision = "0071_anchor_lifecycle_v0557"
down_revision = "0070_benchmark_evidence_v0556"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.57', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.56', updated_at=now() WHERE key='schema_version'"))
