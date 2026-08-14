from getpass import getpass

from pwdlib import PasswordHash

from database import SessionLocal
from models import Admin


password_hasher = PasswordHash.recommended()


def create_admin():
    """
    创建管理员账号。
    """

    username = input(
        "请输入管理员用户名："
    ).strip()

    if not username:
        print("用户名不能为空。")
        return

    password = getpass(
        "请输入管理员密码："
    )

    confirm_password = getpass(
        "请再次输入管理员密码："
    )

    if password != confirm_password:
        print("两次输入的密码不一致。")
        return

    db = SessionLocal()

    try:
        # 检查用户名是否已经存在
        existing_admin = (
            db.query(Admin)
            .filter(Admin.username == username)
            .first()
        )

        if existing_admin:
            print("管理员用户名已经存在。")
            return

        # 对密码进行哈希
        password_hash = password_hasher.hash(
            password
        )

        admin = Admin(
            username=username,
            password_hash=password_hash,
        )

        db.add(admin)

        db.commit()

        db.refresh(admin)

        print(
            f"管理员创建成功，ID：{admin.id}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()