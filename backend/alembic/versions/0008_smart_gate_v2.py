"""Smart Gate 2.0 counting defaults and V0.3.0 marker.

Revision ID: 0008_smart_gate_v2
Revises: 0007_release_hygiene
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_smart_gate_v2"
down_revision = "0007_release_hygiene"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Lower only the previous untouched default. Explicit user-tuned confidence
    # values are preserved.
    op.execute(sa.text("UPDATE cameras SET confidence_threshold=0.25 WHERE ABS(confidence_threshold - 0.35) < 0.000001"))
    op.execute(sa.text("UPDATE system_settings SET value='0.3.0', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.2.9', updated_at=now() WHERE key='schema_version'"))
