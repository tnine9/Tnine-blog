import os
import secrets
import string

from pwdlib import PasswordHash

from database import SessionLocal
from models import Admin


password_hasher = PasswordHash.recommended()


def generate_strong_password(length: int = 10) -> str:
    """
    生成高强度随机密码（不依赖任何默认/硬编码值）。
    """
    alphabet = (
        string.ascii_letters
        + string.digits
        + "!@#$%^&*"
    )

    # 保证至少包含字母与数字
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
    ]

    password += [
        secrets.choice(alphabet)
        for _ in range(max(length - 3, 0))
    ]

    secrets.SystemRandom().shuffle(password)

    return "".join(password)


def create_admin():
    """
    创建唯一管理员账号 admin。

    - 用户名固定为 admin，不接受自定义
    - 密码优先读取环境变量 TNINE_ADMIN_PASSWORD；
      未设置时生成高强度随机密码并打印（仅本次可见，不落明文）
    - admin 已存在时不覆盖原密码
    """

    db = SessionLocal()

    try:

        existing_admin = (
            db.query(Admin)
            .filter(Admin.username == "admin")
            .first()
        )

        if existing_admin:
            print(
                "管理员账号 admin 已存在，"
                "如需修改密码请使用后台功能，本脚本不会覆盖。"
            )
            return

        password = os.environ.get(
            "TNINE_ADMIN_PASSWORD", ""
        ).strip()

        if not password:
            password = generate_strong_password()

            print(
                "未设置环境变量 TNINE_ADMIN_PASSWORD，"
                "已生成随机初始密码（仅本次显示一次）："
            )

            print(f">>> {password} <<<")

        password_hash = password_hasher.hash(password)

        admin = Admin(
            username="admin",
            password_hash=password_hash,
            nickname="成哥",
        )

        db.add(admin)

        db.commit()

        db.refresh(admin)

        print(
            f"管理员创建成功，ID：{admin.id}，用户名：admin（密码已 Hash 存储）"
        )

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
