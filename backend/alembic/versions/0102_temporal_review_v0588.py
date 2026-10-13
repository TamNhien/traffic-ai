"""V0.5.88: temporal review contract fix; metadata only, no schema changes."""
from alembic import op
import sqlalchemy as sa
revision = "0102_temporal_review_v0588"
down_revision = "0101_benchmark_compare_v0587"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.88', updated_at=now() WHERE key='schema_version'"))

def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.87', updated_at=now() WHERE key='schema_version'"))
