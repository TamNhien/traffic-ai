"""Traffic AI authentication primitives: Argon2id, opaque sessions, CSRF and RBAC."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import re
import secrets
import unicodedata

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import select

from app.models.all_models import AuthSession, LoginLimit, SecurityAudit, User

COOKIE_NAME = "__Host-traffic_ai_session"
ROLES = {"admin", "operator", "viewer"}
PASSWORD_MIN_LENGTH = 12
SESSION_HOURS = 8
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16, type=Type.ID)
# Spend approximately the same verification work when the username does not exist.
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(35))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def require_password(password: str) -> str:
    if not (PASSWORD_MIN_LENGTH <= len(password) <= 128) or len(password.encode("utf-8")) > 512:
        raise ValueError("Mật khẩu phải có 12–128 ký tự và không quá 512 byte UTF-8")
    categories = {unicodedata.category(char) for char in password}
    if not ("Lu" in categories and "Ll" in categories and "Nd" in categories
            and any(category.startswith(("P", "S")) for category in categories)):
        raise ValueError("Mật khẩu cần có chữ hoa, chữ thường, số và ký tự đặc biệt")
    return password


def hash_password(password: str) -> str:
    return HASHER.hash(require_password(password))


def verify_password(stored: str, password: str) -> bool:
    try:
        return HASHER.verify(stored, password)
    except (VerificationError, InvalidHashError, ValueError, TypeError):
        return False


def password_needs_rehash(stored: str) -> bool:
    return HASHER.check_needs_rehash(stored)


def csrf_from_session_token(token: str) -> str:
    return hmac.new(token.encode("utf-8"), b"traffic-ai-csrf-v1", "sha256").hexdigest()


def new_session(db, user: User) -> tuple[str, str, AuthSession]:
    token = secrets.token_urlsafe(32)
    csrf = csrf_from_session_token(token)
    session = AuthSession(user_id=user.id, token_hash=digest(token), csrf_hash=digest(csrf), expires_at=now_utc() + timedelta(hours=SESSION_HOURS))
    db.add(session)
    db.flush()
    return token, csrf, session


def lookup_session(db, raw_token: str | None):
    if not raw_token or len(raw_token) > 256:
        return None
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == digest(raw_token)))
    if session is None or session.revoked_at is not None or aware(session.expires_at) <= now_utc():
        return None
    user = db.get(User, session.user_id)
    return (user, session) if user and user.is_active else None


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def valid_csrf(session: AuthSession, raw_csrf: str | None) -> bool:
    return bool(raw_csrf and len(raw_csrf) <= 256 and hmac.compare_digest(session.csrf_hash, digest(raw_csrf)))


def allowed(user: User, method: str, path: str) -> bool:
    if path in {"/api/auth/me", "/api/auth/check", "/api/auth/change-password", "/api/auth/logout", "/api/auth/logout-all"}:
        return True
    if user.role == "admin":
        return True
    if path.startswith('/api/admin/'):
        return False
    if user.role == "operator":
        return True
    if path.endswith("/export") or path.startswith("/api/sources/") or path.startswith("/api/datasets/") and "/images/" in path:
        return False
    return method in {"GET", "HEAD", "OPTIONS"}


def throttle_key(username: str, address: str) -> str:
    return digest(username.casefold() + "|" + address)


def get_limit(db, key: str, current: datetime) -> LoginLimit:
    row = db.scalar(select(LoginLimit).where(LoginLimit.key_hash == key).with_for_update())
    if row is None:
        row = LoginLimit(key_hash=key, failures=0, window_started=current)
        db.add(row)
        db.flush()
    if aware(row.window_started) < current - timedelta(minutes=15):
        row.failures = 0
        row.window_started = current
        row.locked_until = None
    return row


def blocked(limit: LoginLimit, current: datetime) -> bool:
    return bool(limit.locked_until and aware(limit.locked_until) > current)


def fail_limit(limit: LoginLimit, current: datetime) -> None:
    limit.failures += 1
    if limit.failures >= 5:
        limit.locked_until = current + timedelta(minutes=15)


def audit(db, *, user=None, action: str, resource: str = "", outcome: str = "ok", ip: str = "") -> None:
    db.add(SecurityAudit(user_id=getattr(user,"id",None), username=getattr(user,"username",None),
                         action=action[:100], resource=resource[:300], outcome=outcome[:24], ip_hash=digest(ip) if ip else None))


def public_user(user: User) -> dict:
    return {"id":user.id,"username":user.username,"full_name":user.full_name,
            "role":user.role,"is_active":user.is_active,"must_change_password":user.must_change_password,
            "created_at":user.created_at,"last_login_at":user.last_login_at}
