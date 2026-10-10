"""Explicit first-admin bootstrap. No default passwords or open registration endpoint."""
from getpass import getpass
from sqlalchemy import select, func
from app.db.session import SessionLocal
from app.models.all_models import User
from app.security import hash_password


def main():
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User).where(User.role=="admin", User.is_active.is_(True))):
            raise SystemExit("Đã có Admin đang hoạt động. Dùng giao diện để quản lý tài khoản.")
        username = input("Tên đăng nhập Admin (3–80 ký tự, ASCII): ").strip()
        import re
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}",username):
            raise SystemExit("Username không hợp lệ")
        if db.scalar(select(User).where(func.lower(User.username)==username.lower())):
            raise SystemExit("Username đã tồn tại")
        password = getpass("Mật khẩu (12–128 ký tự, hoa + thường + số + ký tự đặc biệt): ")
        repeated = getpass("Nhập lại mật khẩu: ")
        if password != repeated:
            raise SystemExit("Hai mật khẩu không khớp")
        try:
            encoded = hash_password(password)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        db.add(User(username=username, full_name="Quản trị viên", password_hash=encoded, role="admin", is_active=True))
        db.commit()
        print("Đã tạo Admin. Hãy đăng nhập qua HTTPS và bật bảo vệ thiết bị quản trị.")

if __name__ == "__main__":
    main()
