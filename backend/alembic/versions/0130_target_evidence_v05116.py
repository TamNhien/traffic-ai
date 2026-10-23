"""V0.5.116 target evidence policies; release metadata only."""
from alembic import op
import sqlalchemy as sa

revision = '0130_target_evidence_v05116'
down_revision = '0129_review_tracks_v05115'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.116', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE system_settings SET value='0.5.115', updated_at=now() WHERE key='schema_version'"))
