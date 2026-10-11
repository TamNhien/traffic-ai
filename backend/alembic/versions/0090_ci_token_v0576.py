"""V0.5.76 CI test environment regression fix.

Only version metadata changes: no data, users, AI token or counting logic changed.
"""
from alembic import op
import sqlalchemy as sa

revision = "0090_ci_token_v0576"
down_revision = "0089_replay_drift_v0575"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.76', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.75', updated_at=now() WHERE key='schema_version'"))
