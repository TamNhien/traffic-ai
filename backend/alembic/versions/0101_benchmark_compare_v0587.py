"""V0.5.87: verified benchmark compare tools and temporal audit UX; metadata only."""
from alembic import op
import sqlalchemy as sa
revision = "0101_benchmark_compare_v0587"
down_revision = "0100_incumbent_reservation_v0586"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.87', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.86', updated_at=now() WHERE key='schema_version'"))
