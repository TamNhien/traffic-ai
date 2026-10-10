"""Global fail-closed access control, including routes added in future modules."""
from __future__ import annotations
from fastapi import Request
from fastapi.responses import JSONResponse
from app.db.session import SessionLocal
from app.security import allowed, audit, lookup_session, valid_csrf, COOKIE_NAME

PUBLIC = {"/api/health", "/api/auth/login"}
DOCS = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        # Browsers ordinarily send Origin for unsafe fetches. Strictly require it.
        return False
    host = request.headers.get("host", "")
    return origin == f"https://{host}"


async def enforce_auth(request: Request, call_next):
    path, method = request.url.path, request.method
    target = path.startswith("/api/") or path in DOCS
    if not target:
        return await call_next(request)
    if method == "OPTIONS":
        return await call_next(request)
    if path == "/api/health":
        return await call_next(request)
    # Trusted Docker-network worker RPC is authenticated by the route's
    # constant-time AI shared-token guard, not browser cookies / CSRF.
    # Both public HTTPS gateway server blocks DENY /api/internal/ completely.
    if path.startswith("/api/internal/"):
        return await call_next(request)
    if path == "/api/auth/login":
        if method != "POST":
            return JSONResponse({"detail":"Method Not Allowed"}, status_code=405)
        if not same_origin(request) or "application/json" not in request.headers.get("content-type",""):
            return JSONResponse({"detail":"Invalid login origin/content type"},status_code=403)
        return await call_next(request)
    with SessionLocal() as db:
        found = lookup_session(db, request.cookies.get(COOKIE_NAME))
        if not found:
            return JSONResponse({"detail":"Authentication required"},status_code=401,headers={"Cache-Control":"no-store"})
        user, session = found
        if not allowed(user,method,path):
            return JSONResponse({"detail":"Insufficient permissions"},status_code=403)
        if user.must_change_password and path not in {"/api/auth/me", "/api/auth/check", "/api/auth/change-password", "/api/auth/logout", "/api/auth/logout-all"}:
            return JSONResponse({"detail":"Bạn phải đổi mật khẩu ban đầu"},status_code=403)
        if method in UNSAFE:
            if not same_origin(request) or not valid_csrf(session, request.headers.get("x-csrf-token")):
                return JSONResponse({"detail":"CSRF verification failed"},status_code=403)
        request.state.auth_user = user
        request.state.auth_session = session
        actor_id, username = user.id, user.username
    response = await call_next(request)
    if method in UNSAFE and path not in {"/api/auth/logout", "/api/auth/change-password"}:
        # Record metadata only: never record query string, request body, secrets or tokens.
        try:
            with SessionLocal() as db:
                from app.models.all_models import User
                actor = db.get(User, actor_id)
                audit(db,user=actor,action=f"api.{method.lower()}", resource=path[:300],
                      outcome="ok" if response.status_code < 400 else "error")
                db.commit()
        except Exception:
            # Failed audit must not accidentally turn a committed camera action into a retry.
            pass
    response.headers.setdefault("Cache-Control", "no-store" if path.startswith("/api/") else "private")
    return response
