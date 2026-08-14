from database import SessionLocal
from models import Article


def init_articles():
    """
    创建一篇测试文章。
    """

    db = SessionLocal()

    try:

        article = Article(
            title="我的第一篇博客",

            summary=(
                "这是我的第一篇真正存进数据库的文章。"
            ),

            content="""
今天是我开始开发博客的第一天。

之前我们已经完成了 FastAPI、
Jinja2、HTML、CSS 和文章详情页。

现在，我们正式把文章保存到 SQLite 数据库中。

这意味着以后文章不需要再写死在 Python 代码里。
        """.strip(),

            # 测试文章默认直接发布
            status="published",
        )

        db.add(article)

        db.commit()

        db.refresh(article)

        print(
            f"文章创建成功，ID：{article.id}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    init_articles()