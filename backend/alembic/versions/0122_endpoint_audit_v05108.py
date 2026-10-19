"""V0.5.108 actual endpoint suppression audit; schema metadata only."""
from alembic import op
import sqlalchemy as sa

revision = "0122_endpoint_audit_v05108"
down_revision = "0121_test_runner_v05107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.108', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.107', updated_at=now() WHERE key='schema_version'"))
