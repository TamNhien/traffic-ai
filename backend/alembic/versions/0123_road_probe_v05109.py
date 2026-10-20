"""V0.5.109 read-only road eligibility and finite gate telemetry."""
from alembic import op
import sqlalchemy as sa

revision = "0123_road_probe_v05109"
down_revision = "0122_endpoint_audit_v05108"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.109', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.108', updated_at=now() WHERE key='schema_version'"))
