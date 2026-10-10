"""V0.5.68 regression: end-to-end session/CSRF/RBAC with SQLite test database."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.all_models import User, AuthSession
from app.security import hash_password, verify_password, require_password, HASHER, lookup_session, allowed
import app.auth_middleware as auth_middleware


@pytest.fixture()
def auth_env(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread":False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(auth_middleware,"SessionLocal",factory)
    def override_db():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    with factory() as db:
        db.add_all([
            User(username="admin",full_name="Admin", role="admin", password_hash=hash_password("AdminPassword2026"),is_active=True),
            User(username="viewer",full_name="Viewer", role="viewer", password_hash=hash_password("ViewerPassword2026"),is_active=True),
            User(username="operator",full_name="Operator", role="operator", password_hash=hash_password("OperatorPassword2026"),is_active=True),
        ])
        db.commit()
    client = TestClient(app, base_url="https://testserver")
    try:
        yield client, factory
    finally:
        client.close()
        app.dependency_overrides.pop(get_db,None)
        engine.dispose()


def signin(client,username,password):
    return client.post('/api/auth/login',json={'username':username,'password':password},headers={'Origin':'https://testserver'})


def mutation(client,path,method='POST',csrf='',body=None):
    return client.request(method,path,json=body or {},headers={'Origin':'https://testserver','X-CSRF-Token':csrf})


def test_v0568_password_argon2id_and_weak_password_rejection():
    first=hash_password('StrongPassword2026')
    second=hash_password('StrongPassword2026')
    assert first.startswith('$argon2id$') and first!=second
    assert verify_password(first,'StrongPassword2026')
    assert not verify_password(first,'WrongPassword2026')
    assert not verify_password('malformed','StrongPassword2026')
    with pytest.raises(ValueError):
        require_password('short')
    with pytest.raises(ValueError):
        require_password('lettersbutnodigits')
    assert HASHER.memory_cost == 65536 and HASHER.time_cost == 3


def test_v0568_unauthenticated_api_denied_but_health_open(auth_env):
    client,_ = auth_env
    assert client.get('/api/cameras').status_code == 401
    assert client.get('/api/admin/users').status_code == 401
    assert client.get('/api/health').status_code == 200
    assert client.post('/api/cameras',json={}).status_code == 401
    assert client.get('/docs').status_code == 401


def test_v0568_login_requires_same_origin_and_sets_host_cookie(auth_env):
    client,factory=auth_env
    assert client.post('/api/auth/login',json={'username':'admin','password':'AdminPassword2026'}).status_code == 403
    assert client.post('/api/auth/login',headers={'Origin':'https://evil.example'},json={'username':'admin','password':'AdminPassword2026'}).status_code == 403
    res=signin(client,'admin','AdminPassword2026')
    assert res.status_code==200
    assert '__Host-traffic_ai_session=' in res.headers['set-cookie']
    assert 'httponly' in res.headers['set-cookie'].lower()
    assert 'secure' in res.headers['set-cookie'].lower()
    assert 'samesite=strict' in res.headers['set-cookie'].lower()
    assert 'password_hash' not in res.text
    assert 'csrf_token' in res.json()
    assert client.get('/api/auth/me').json()['user']['role']=='admin'
    with factory() as db:
        session=db.scalar(select(AuthSession))
        assert session.token_hash!=client.cookies.get('__Host-traffic_ai_session')
        assert session.csrf_hash != res.json()['csrf_token']


def test_v0568_csrf_and_role_enforced_server_side(auth_env):
    client,_=auth_env
    csrf=signin(client,'viewer','ViewerPassword2026').json()['csrf_token']
    assert client.get('/api/admin/users').status_code==403
    assert mutation(client,'/api/admin/users',csrf=csrf,body={}).status_code==403
    assert client.get('/api/cameras').status_code==200
    assert mutation(client,'/api/auth/logout',csrf='bogus').status_code==403
    assert mutation(client,'/api/auth/logout',csrf=csrf).status_code==200
    assert client.get('/api/auth/me').status_code==401


def test_v0568_admin_create_role_lock_and_password_reset(auth_env):
    client,factory=auth_env
    csrf=signin(client,'admin','AdminPassword2026').json()['csrf_token']
    created=mutation(client,'/api/admin/users',csrf=csrf,body={
        'username':'newtech','full_name':'Technician','role':'operator','password':'TempPassword2026'})
    assert created.status_code==201 and created.json()['must_change_password'] is True
    uid=created.json()['id']
    assert mutation(client,f'/api/admin/users/{uid}',method='PATCH',csrf=csrf,body={'role':'viewer'}).status_code==200
    assert mutation(client,'/api/admin/users/1',method='PATCH',csrf=csrf,body={'is_active':False}).status_code==409
    assert mutation(client,f'/api/admin/users/{uid}',method='PATCH',csrf=csrf,body={'is_active':False}).status_code==200
    assert signin(client,'newtech','TempPassword2026').status_code==401
    assert mutation(client,f'/api/admin/users/{uid}',method='PATCH',csrf=csrf,body={'is_active':True}).status_code==200
    assert mutation(client,f'/api/admin/users/{uid}/reset-password',csrf=csrf,body={'new_password':'UpdatedPassword2026'}).status_code==200
    assert signin(client,'newtech','UpdatedPassword2026').status_code==200
    assert client.get('/api/cameras').status_code==403  # must change temporary password first


def test_v0568_login_rate_limit(auth_env):
    client,_=auth_env
    for _ in range(5):
        assert signin(client,'viewer','invalidpassword').status_code==401
    assert signin(client,'viewer','ViewerPassword2026').status_code==429


def test_v0568_change_password_revokes_session(auth_env):
    client,factory=auth_env
    csrf=signin(client,'operator','OperatorPassword2026').json()['csrf_token']
    assert mutation(client,'/api/auth/change-password',csrf=csrf,body={
        'current_password':'OperatorPassword2026','new_password':'NewOperatorPass2026'}).status_code==200
    assert client.get('/api/auth/me').status_code==401
    assert signin(client,'operator','OperatorPassword2026').status_code==401
    assert signin(client,'operator','NewOperatorPass2026').status_code==200


def test_v0568_viewer_can_revoke_every_session(auth_env):
    client,_=auth_env
    csrf=signin(client,'viewer','ViewerPassword2026').json()['csrf_token']
    assert mutation(client,'/api/auth/logout-all',csrf=csrf).status_code==200
    assert client.get('/api/auth/me').status_code==401


def test_v0568_admin_can_revoke_operator_sessions(auth_env):
    client,_=auth_env
    operator_csrf=signin(client,'operator','OperatorPassword2026').json()['csrf_token']
    assert client.get('/api/auth/me').status_code==200
    admin_csrf=signin(client,'admin','AdminPassword2026').json()['csrf_token']
    assert mutation(client,'/api/admin/users/3/revoke-sessions',csrf=admin_csrf).status_code==200
    assert signin(client,'operator','OperatorPassword2026').status_code==200  # new login still works



def test_v0568_internal_ai_rpc_does_not_require_browser_cookie(auth_env):
    client,_=auth_env
    # Validation 422 (not middleware 401/403) proves AI worker delivery path remains reachable.
    result=client.post('/api/internal/events',json={},headers={'X-AI-Token':'invalid'})
    assert result.status_code == 422
