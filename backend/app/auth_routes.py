"""Explicitly authenticated account management; never return stored password hashes."""
from __future__ import annotations
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.all_models import User, AuthSession, SecurityAudit
from app.security import (COOKIE_NAME, allowed, audit, blocked, digest, fail_limit, get_limit,
                          hash_password, lookup_session, new_session, now_utc, password_needs_rehash,
                          public_user, require_password, throttle_key, verify_password, DUMMY_HASH)

router = APIRouter(prefix="/api")


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=512)


class NewUser(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str = Field(min_length=1, max_length=160)
    role: Literal["admin", "operator", "viewer"] = "viewer"
    password: str = Field(min_length=12, max_length=128)


class UserEdit(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    role: Literal["admin", "operator", "viewer"] | None = None
    is_active: bool | None = None


class ChangePassword(BaseModel):
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=12, max_length=128)


class ResetPassword(BaseModel):
    new_password: str = Field(min_length=12, max_length=128)


def admin(request: Request) -> User:
    user = getattr(request.state, "auth_user", None)
    if user is None or user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên được thực hiện")
    return user


def current(request: Request) -> User:
    user = getattr(request.state, "auth_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    return user


def revoke_all(db: Session, user_id: int) -> None:
    for session in db.scalars(select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))):
        session.revoked_at = now_utc()


@router.post("/auth/login")
def login(payload: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    username = payload.username.strip()
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
    current_time = now_utc()
    # Separate per-address and per-account budgets make credential stuffing harder.
    limits = [get_limit(db, throttle_key("@ip", ip), current_time),
              get_limit(db, throttle_key(username.casefold(), "@account"), current_time)]
    if any(blocked(x, current_time) for x in limits):
        db.commit()
        raise HTTPException(status_code=429, detail="Thử lại sau 15 phút")
    user = db.scalar(select(User).where(func.lower(User.username) == username.lower()))
    ok = verify_password(user.password_hash if user else DUMMY_HASH, payload.password)
    if not ok or not user or not user.is_active:
        for item in limits:
            fail_limit(item, current_time)
        audit(db, action="auth.login", resource="login", outcome="denied", ip=ip)
        db.commit()
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không hợp lệ")
    for item in limits:
        item.failures = 0
        item.locked_until = None
        item.window_started = current_time
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    token, csrf, _ = new_session(db, user)
    user.last_login_at = current_time
    audit(db, user=user, action="auth.login", resource="login", ip=ip)
    db.commit()
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=True, samesite="strict", path="/", max_age=8*3600)
    response.headers["Cache-Control"] = "no-store"
    return {"user":public_user(user),"csrf_token":csrf}


@router.get("/auth/me")
def me(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    user = current(request)
    from app.security import csrf_from_session_token
    csrf = csrf_from_session_token(request.cookies["__Host-traffic_ai_session"])
    response.headers["Cache-Control"] = "no-store"
    return {"user":public_user(user),"csrf_token":csrf}


@router.get("/auth/check")
def check(request: Request, role: str | None = None) -> dict:
    user = current(request)
    if user.must_change_password:
        raise HTTPException(403, detail="Password change required")
    if role == "operator" and user.role not in {"operator", "admin"}:
        raise HTTPException(403, detail="Operator required")
    return {"status":"ok"}


@router.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    user = current(request)
    db.get(AuthSession, request.state.auth_session.id).revoked_at = now_utc()
    audit(db, user=user, action="auth.logout")
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")
    return {"status":"ok"}


@router.post("/auth/logout-all")
def logout_all(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    user = current(request)
    revoke_all(db, user.id)
    audit(db, user=user, action="auth.logout_all")
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="strict")
    return {"status":"ok"}


@router.post("/auth/change-password")
def change_password(payload: ChangePassword, request: Request, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, current(request).id)
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(401, detail="Mật khẩu hiện tại không đúng")
    try:
        new_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    if verify_password(user.password_hash, payload.new_password):
        raise HTTPException(422, detail="Không được sử dụng lại mật khẩu cũ")
    user.password_hash = new_hash
    user.must_change_password = False
    revoke_all(db, user.id)
    audit(db, user=user, action="auth.change_password")
    db.commit()
    return {"status":"ok", "reauthenticate":True}


@router.get("/admin/users")
def list_users(request: Request, db: Session = Depends(get_db)) -> list[dict]:
    admin(request)
    return [public_user(u) for u in db.scalars(select(User).order_by(User.id)).all()]


@router.post("/admin/users", status_code=201)
def create_user(payload: NewUser, request: Request, db: Session = Depends(get_db)) -> dict:
    actor = admin(request)
    if db.scalar(select(User).where(func.lower(User.username) == payload.username.lower())):
        raise HTTPException(409, detail="Tên đăng nhập đã tồn tại")
    try:
        digest_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    user = User(username=payload.username, full_name=payload.full_name.strip(), role=payload.role,
                password_hash=digest_hash, is_active=True, must_change_password=True)
    db.add(user)
    db.flush()
    audit(db, user=actor, action="users.create", resource=f"user:{user.id}")
    db.commit()
    return public_user(user)


def enabled_admin_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))) or 0


@router.patch("/admin/users/{user_id}")
def update_user(user_id: int, payload: UserEdit, request: Request, db: Session = Depends(get_db)) -> dict:
    actor = admin(request)
    # Serialize concurrent administrator demotions/locks before checking last-admin invariant.
    list(db.scalars(select(User).where(User.role == "admin", User.is_active.is_(True)).with_for_update()))
    target = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if target is None:
        raise HTTPException(404, detail="Không tìm thấy người dùng")
    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.full_name is not None:
        target.full_name = payload.full_name.strip()
    if target.id == actor.id and (not target.is_active or target.role != "admin"):
        raise HTTPException(409, detail="Không thể tự khóa hoặc hạ quyền quản trị của mình")
    # Other-admin changes cannot remove the last active admin.
    if enabled_admin_count(db) == 0:
        raise HTTPException(409, detail="Hệ thống phải có ít nhất một Admin đang hoạt động")
    revoke_all(db, target.id)
    audit(db, user=actor, action="users.update", resource=f"user:{user_id}")
    db.commit()
    return public_user(target)


@router.post("/admin/users/{user_id}/reset-password")
def reset_password(user_id: int, payload: ResetPassword, request: Request, db: Session = Depends(get_db)) -> dict:
    actor = admin(request)
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, detail="Không tìm thấy người dùng")
    try:
        target.password_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    target.must_change_password = True
    revoke_all(db, user_id)
    audit(db, user=actor, action="users.reset_password", resource=f"user:{user_id}")
    db.commit()
    return {"status":"ok"}


@router.post("/admin/users/{user_id}/revoke-sessions")
def revoke_user_sessions(user_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    actor = admin(request)
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, detail="Không tìm thấy người dùng")
    revoke_all(db, user_id)
    audit(db,user=actor,action="users.revoke_sessions",resource=f"user:{user_id}")
    db.commit()
    return {"status":"ok"}


@router.get("/admin/audit")
def list_audit(request: Request, limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    admin(request)
    rows = db.scalars(select(SecurityAudit).order_by(SecurityAudit.id.desc()).limit(max(1,min(limit,500)))).all()
    return [{"id":r.id,"username":r.username,"action":r.action,"resource":r.resource,
             "outcome":r.outcome,"created_at":r.created_at} for r in rows]
