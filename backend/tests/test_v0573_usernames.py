"""V0.5.73: Unicode account creation, durable reads, login and clear failures."""
from __future__ import annotations
from sqlalchemy import select
from app.models.all_models import User
from app.usernames import validate_username, username_key
from test_auth_security import auth_env, signin, mutation
import pytest


def test_v0573_unicode_username_validation():
    assert validate_username('  Đạt  ') == 'Đạt'
    assert validate_username('Nhie\u0302n') == 'Nhiên'
    assert username_key('ĐẠT') == username_key('Đạt')
    assert username_key('Nhie\u0302n') == username_key('Nhiên')
    for value in ('ab', 'Đạt Họ', '\u200bĐạt', 'admin!', '../admin', 'test-', '🙃yay'):
        with pytest.raises(ValueError):
            validate_username(value)


def test_v0573_unicode_user_creation_visible_and_can_login(auth_env):
    client, factory=auth_env
    csrf=signin(client,'admin','AdminPassword2026!').json()['csrf_token']
    response=mutation(client, '/api/admin/users', csrf=csrf,body={
        'username':'  Đạt  ', 'full_name':'Phạm Vĩnh Đạt', 'role':'viewer',
        'password':'TempPassword2026!'
    })
    assert response.status_code==201, response.text
    account=response.json()
    assert account['username']=='Đạt' and account['id']>0 and account['must_change_password']
    users=client.get('/api/admin/users')
    assert users.status_code==200
    assert len([u for u in users.json() if u['username']=='Đạt'])==1
    with factory() as db:
        user=db.scalar(select(User).where(User.username_key==username_key('đẠt')))
        assert user and user.id==account['id'] and user.full_name=='Phạm Vĩnh Đạt'
    duplicate=mutation(client,'/api/admin/users',csrf=csrf,body={
        'username':'đẠT','full_name':'Duplicate', 'role':'viewer','password':'TempPassword2026!'
    })
    assert duplicate.status_code==409
    assert duplicate.json()['detail']=='Tên đăng nhập đã tồn tại'
    assert signin(client,'ĐẠT','TempPassword2026!').status_code==200
    assert signin(client,'Đạt','TempPassword2026!').status_code==200


def test_v0573_invalid_username_validation_structured(auth_env):
    client,_=auth_env
    csrf=signin(client,'admin','AdminPassword2026!').json()['csrf_token']
    res=mutation(client,'/api/admin/users',csrf=csrf,body={
        'username':'Đạt test','full_name':'Phạm Vĩnh Đạt','role':'viewer','password':'TempPassword2026!'
    })
    assert res.status_code==422
    assert isinstance(res.json()['detail'],list)
    assert client.get('/api/admin/users').status_code==200
    assert all(u['username']!='Đạt test' for u in client.get('/api/admin/users').json())
