# -*- coding: utf-8 -*-
"""
Tnine 后台重构 v2 迁移脚本（幂等，可重复执行）

变更点：
1. Admin.nickname 取消默认昵称：若仍是默认值"成哥"则置空（保留用户已修改的真实昵称）
2. Admin 新增 bio 列（个人简介，slogan 来源）
3. SocialLink 新增 link_type / qr_code 列（链接 / 二维码两种展示方式）
4. 新增 notifications 表（通知系统）
5. Setting 新增 8 个页面信息配置默认值
   （home/article/moment/message 各 title+description）
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "blog.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn, table):
    return {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})")
    }


def migrate():
    conn = get_conn()
    try:
        conn.execute("BEGIN")

        # ---------- 1. Admin.nickname 取消默认昵称 ----------
        admins_cols = table_columns(conn, "admins")
        if "bio" not in admins_cols:
            conn.execute(
                "ALTER TABLE admins ADD COLUMN bio VARCHAR(200) NOT NULL DEFAULT ''"
            )
            print("[OK] admins 新增 bio 列")
        else:
            print("[SKIP] admins.bio 已存在")

        # 仅将从未修改过的默认昵称"成哥"置空；真实昵称保留
        cur = conn.execute(
            "UPDATE admins SET nickname = '' WHERE nickname = '成哥'"
        )
        if cur.rowcount:
            print(f"[OK] 已清空 {cur.rowcount} 条默认昵称'成哥'（触发首次完善资料流程）")
        else:
            print("[SKIP] 无默认昵称'成哥'需要清空")

        # ---------- 2. SocialLink 新增 link_type / qr_code ----------
        social_cols = table_columns(conn, "social_links")
        if "link_type" not in social_cols:
            conn.execute(
                "ALTER TABLE social_links ADD COLUMN link_type VARCHAR(30) NOT NULL DEFAULT 'link'"
            )
            print("[OK] social_links 新增 link_type 列")
        else:
            print("[SKIP] social_links.link_type 已存在")

        if "qr_code" not in social_cols:
            conn.execute(
                "ALTER TABLE social_links ADD COLUMN qr_code VARCHAR(500) NOT NULL DEFAULT ''"
            )
            print("[OK] social_links 新增 qr_code 列")
        else:
            print("[SKIP] social_links.qr_code 已存在")

        # ---------- 3. notifications 表 ----------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER NOT NULL PRIMARY KEY,
                type VARCHAR(30) NOT NULL,
                target_id INTEGER NOT NULL,
                content VARCHAR(500) NOT NULL,
                is_read BOOLEAN NOT NULL,
                created_at DATETIME
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_notifications_type ON notifications (type)"
        )
        print("[OK] notifications 表就绪")

        # ---------- 4. Setting 页面信息 8 字段默认值 ----------
        page_defaults = {
            "home_title": "Tnine",
            "home_description": "记录代码、生活和探索世界的过程",
            "article_title": "文章",
            "article_description": "记录代码、生活和探索世界的过程",
            "moment_title": "朋友圈",
            "moment_description": "记录代码、生活和探索世界的过程",
            "message_title": "留言",
            "message_description": "记录代码、生活和探索世界的过程",
        }
        for key, value in page_defaults.items():
            exists = conn.execute(
                "SELECT 1 FROM settings WHERE key = ?", (key,)
            ).fetchone()
            if exists is None:
                conn.execute(
                    "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                    (key, value),
                )
                print(f"[OK] settings 新增 {key} = {value}")
            else:
                print(f"[SKIP] settings.{key} 已存在")

        conn.commit()
        print("\n[完成] Tnine v2 迁移成功")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
