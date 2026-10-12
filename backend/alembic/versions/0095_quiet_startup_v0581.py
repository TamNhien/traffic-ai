"""V0.5.81: quiet bounded startup and test-only pip warning policy; version only."""
from alembic import op
import sqlalchemy as sa

revision = "0095_quiet_startup_v0581"
down_revision = "0094_incumbent_identity_v0580"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.81', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.80', updated_at=now() WHERE key='schema_version'"))
