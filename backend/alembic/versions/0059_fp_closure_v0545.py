"""False Positive Closure 9.1 + long-gap rescue guard V0.5.45.

Revision ID: 0059_fp_closure_v0545
Revises: 0058_benchmark_review_v0544
"""
from alembic import op
import sqlalchemy as sa

revision = "0059_fp_closure_v0545"
down_revision = "0058_benchmark_review_v0544"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.45', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.44', updated_at=now() WHERE key='schema_version'"))
