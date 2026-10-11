"""Explicit first-admin bootstrap. No default passwords or open registration endpoint."""
from getpass import getpass
from sqlalchemy import select, func
from app.db.session import SessionLocal
from app.models.all_models import User
from app.security import hash_password
from app.usernames import validate_username, username_key


def main():
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User).where(User.role=="admin", User.is_active.is_(True))):
            raise SystemExit("Đã có Admin đang hoạt động. Dùng giao diện để quản lý tài khoản.")
        try:
            username = validate_username(input("Tên đăng nhập Admin (3–80 ký tự, hỗ trợ tiếng Việt): "))
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if db.scalar(select(User).where(User.username_key == username_key(username))):
            raise SystemExit("Username đã tồn tại")
        password = getpass("Mật khẩu (12–128 ký tự, hoa + thường + số + ký tự đặc biệt): ")
        repeated = getpass("Nhập lại mật khẩu: ")
        if password != repeated:
            raise SystemExit("Hai mật khẩu không khớp")
        try:
            encoded = hash_password(password)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        db.add(User(username=username, username_key=username_key(username), full_name="Quản trị viên", password_hash=encoded, role="admin", is_active=True))
        db.commit()
        print("Đã tạo Admin. Hãy đăng nhập qua HTTPS và bật bảo vệ thiết bị quản trị.")

if __name__ == "__main__":
    main()
