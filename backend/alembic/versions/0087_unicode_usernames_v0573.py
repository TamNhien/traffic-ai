"""V0.5.73: add canonical Unicode username index, preserving all existing users."""
from alembic import op
import sqlalchemy as sa
import unicodedata

revision = "0087_unicode_usernames_v0573"
down_revision = "0086_replay_guard_v0572"
branch_labels = None
depends_on = None


def _key(value: str) -> str:
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", value.strip()).casefold())


def upgrade() -> None:
    op.add_column("users", sa.Column("username_key", sa.String(80), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, username FROM users ORDER BY id")).fetchall()
    seen = {}
    for user_id, name in rows:
        key = _key(name)
        if not key or len(key) > 80 or key in seen:
            raise RuntimeError(f"Trùng tài khoản Unicode sau chuẩn hóa: user {seen.get(key)} và {user_id}. Cần xử lý trước migration.")
        seen[key] = user_id
        bind.execute(sa.text("UPDATE users SET username_key=:key WHERE id=:id"), {"key": key, "id": user_id})
    op.alter_column("users", "username_key", nullable=False)
    op.create_index("ix_users_username_key", "users", ["username_key"], unique=True)
    op.execute(sa.text("UPDATE system_settings SET value='0.5.73', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.drop_index("ix_users_username_key", table_name="users")
    op.drop_column("users", "username_key")
    op.execute(sa.text("UPDATE system_settings SET value='0.5.72', updated_at=now() WHERE key='schema_version'"))
