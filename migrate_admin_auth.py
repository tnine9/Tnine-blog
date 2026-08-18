"""
管理员认证系统迁移脚本。

目标：为已有的 admins 表补充新认证系统所需字段，不删除任何现有数据：
- email        VARCHAR(255) NULL  ：管理员收件邮箱（用于接收登录验证码）
- created_at   DATETIME     NULL  ：管理员记录创建时间

用法：
    python migrate_admin_auth.py

参考 migrate_draft.py 的做法：
- 先 PRAGMA table_info 检查字段，已存在则跳过
- 仅 ALTER TABLE ADD COLUMN，不重建表、不删除数据
"""

from sqlalchemy import text

from database import engine


def migrate():
    with engine.begin() as conn:

        # 检查 admins 表的字段
        result = conn.execute(
            text("PRAGMA table_info(admins)")
        )

        columns = [
            row[1]
            for row in result
        ]

        added = []

        # email 字段
        if "email" in columns:
            print("email 字段已经存在，不需要迁移。")
        else:
            conn.execute(
                text(
                    """
                    ALTER TABLE admins
                    ADD COLUMN email VARCHAR(255)
                    """
                )
            )
            added.append("email")

        # created_at 字段
        if "created_at" in columns:
            print("created_at 字段已经存在，不需要迁移。")
        else:
            conn.execute(
                text(
                    """
                    ALTER TABLE admins
                    ADD COLUMN created_at DATETIME
                    """
                )
            )
            added.append("created_at")

        if added:
            print(
                "数据库迁移成功：admins 表已添加字段："
                + ", ".join(added)
                + "。"
            )
        else:
            print(
                "admins 表无需迁移，字段已齐全。"
            )

        # ==================================================
        # 固定管理员账号迁移
        # 新认证系统要求：唯一管理员账号 username 固定为 admin
        # 若 admins 表存在非 admin 账号（如旧的 "Tnine"），
        # 且不存在 username=admin 的记录，则将其改名为 admin
        # （保留原密码哈希与昵称，不删除任何数据）
        # ==================================================

        result = conn.execute(
            text(
                """
                SELECT id, username FROM admins
                ORDER BY id ASC
                """
            )
        )

        rows = result.fetchall()

        has_admin = any(
            row[1] == "admin"
            for row in rows
        )

        non_admin_rows = [
            row
            for row in rows
            if row[1] != "admin"
        ]

        if has_admin:

            if non_admin_rows:

                print(
                    "警告：admins 表已存在 username=admin 的记录，"
                    "其余账号未处理（新系统仅使用 admin 账号）。"
                )

        elif non_admin_rows:

            first_id = non_admin_rows[0][0]

            old_username = non_admin_rows[0][1]

            conn.execute(
                text(
                    """
                    UPDATE admins
                    SET username = 'admin'
                    WHERE id = :admin_id
                    """
                ),
                {"admin_id": first_id},
            )

            print(
                "数据库迁移成功：管理员账号 "
                + old_username
                + " 已更名为 admin（保留原密码与昵称）。"
            )

            if len(non_admin_rows) > 1:

                print(
                    "警告：admins 表存在多个账号，"
                    "新系统仅使用 admin，其余账号未改动。"
                )

        else:

            print(
                "admins 表当前没有管理员账号，"
                "将由首次初始化流程创建 admin。"
            )


if __name__ == "__main__":
    migrate()
