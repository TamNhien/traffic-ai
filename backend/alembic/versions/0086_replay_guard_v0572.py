"""Deterministic replay / benchmark release guard V0.5.72 (metadata only)."""
from alembic import op
import sqlalchemy as sa

revision = "0086_replay_guard_v0572"
down_revision = "0085_password_policy_v0571"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.72', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.71', updated_at=now() WHERE key='schema_version'"))
