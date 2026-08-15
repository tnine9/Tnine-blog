from sqlalchemy import text

from database import engine


def migrate():
    with engine.begin() as conn:

        # 检查 articles 表的字段
        result = conn.execute(
            text("PRAGMA table_info(articles)")
        )

        columns = [
            row[1]
            for row in result
        ]

        # 如果已经存在 status，就不重复添加
        if "status" in columns:
            print(
                "status 字段已经存在，不需要迁移。"
            )
            return

        # 给已有 articles 表增加 status 字段
        # 原有文章全部默认为 published
        conn.execute(
            text(
                """
                ALTER TABLE articles
                ADD COLUMN status
                VARCHAR(20)
                NOT NULL
                DEFAULT 'published'
                """
            )
        )

        print(
            "数据库迁移成功："
            "已添加 status 字段。"
        )


if __name__ == "__main__":
    migrate()