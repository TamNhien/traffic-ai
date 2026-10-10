"""Argon2id user authorization and session records V0.5.68.

Revision ID: 0082_security_auth_v0568
Revises: 0081_temporal_audit_v0567
"""
from alembic import op
import sqlalchemy as sa

revision = "0082_security_auth_v0568"
down_revision = "0081_temporal_audit_v0567"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(16), server_default="viewer", nullable=False))
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.create_check_constraint("ck_users_role", "users", "role IN ('admin', 'operator', 'viewer')")
    op.create_table("auth_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    for key in ("user_id", "token_hash", "expires_at"):
        op.create_index(f"ix_auth_sessions_{key}", "auth_sessions", [key], unique=key == "token_hash")
    op.create_table("login_limits",
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
    )
    op.create_table("security_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("username", sa.String(80)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource", sa.String(300)),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for key in ("user_id", "action", "created_at"):
        op.create_index(f"ix_security_audit_{key}", "security_audit", [key])
    op.execute(sa.text("UPDATE system_settings SET value='0.5.68', updated_at=now() WHERE key='schema_version'"))


def downgrade() -> None:
    op.drop_table("login_limits")
    for key in ("user_id", "action", "created_at"):
        op.drop_index(f"ix_security_audit_{key}", table_name="security_audit")
    op.drop_table("security_audit")
    for key in ("user_id", "token_hash", "expires_at"):
        op.drop_index(f"ix_auth_sessions_{key}", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_constraint("ck_users_role", "users", type_="check")
    for key in ("last_login_at", "must_change_password", "role"):
        op.drop_column("users", key)
    op.execute(sa.text("UPDATE system_settings SET value='0.5.67', updated_at=now() WHERE key='schema_version'"))
