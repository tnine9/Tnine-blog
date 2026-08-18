# -*- coding: utf-8 -*-
"""
Tnine 文章系统 v1.1 数据库迁移
=================================
1. 为 articles 表增量添加 published_at 列（首次发布时间）
2. 已发布文章回填 published_at = created_at（保持历史展示时间不变）
3. 不删除任何现有数据

幂等：可重复执行，已存在列 / 已回填则跳过。
"""

import sqlite3
import os

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "blog.db",
)


def main():

    if not os.path.exists(DB_PATH):
        print(f"[SKIP] 数据库不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # ====================================================
        # 1. 检查 / 添加 published_at 列
        # ====================================================

        cols = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(articles)"
            ).fetchall()
        }

        if "published_at" not in cols:

            conn.execute(
                "ALTER TABLE articles "
                "ADD COLUMN published_at DATETIME"
            )

            print("[OK] articles.published_at 列已添加")

        else:

            print("[SKIP] articles.published_at 列已存在")

        # ====================================================
        # 2. 已发布文章回填 published_at = created_at
        # ====================================================

        cur = conn.execute(
            """
            UPDATE articles
            SET published_at = created_at
            WHERE status = 'published'
              AND published_at IS NULL
            """
        )

        print(f"[OK] 已回填 published_at 的文章数: {cur.rowcount}")

        # ====================================================
        # 3. 校验
        # ====================================================

        total = conn.execute(
            "SELECT COUNT(*) AS c FROM articles"
        ).fetchone()["c"]

        missing = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM articles
            WHERE status = 'published'
              AND published_at IS NULL
            """
        ).fetchone()["c"]

        print(f"[OK] 文章总数: {total}, 已发布但缺 published_at: {missing}")

        conn.commit()

    finally:

        conn.close()


if __name__ == "__main__":

    main()
