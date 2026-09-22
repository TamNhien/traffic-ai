"""Record counting reliability and replay-safe runtime release.

Revision ID: 0005_counting_reliability
Revises: 0004_runtime_stability
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_counting_reliability"
down_revision: Union[str, None] = "0004_runtime_stability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.2.7', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.2.3', updated_at=now() WHERE key='schema_version'"))
