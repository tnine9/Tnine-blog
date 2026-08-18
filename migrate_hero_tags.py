# -*- coding: utf-8 -*-
"""
Tnine Hero 首屏系统 + 标签系统 数据库迁移脚本

功能：
1. 通过 Base.metadata.create_all 创建新增表（tags / article_tags /
   social_links / hero_backgrounds）。SQLite 下 create_all 对已存在表
   不修改、不重建、不删除数据，仅补建缺失的表。
2. 为 settings 表补充 Hero 默认配置（仅当键不存在时写入，不覆盖已有值）。

用法：
    python migrate_hero_tags.py
"""

from datetime import datetime

from database import Base, SessionLocal, engine
from models import Setting


DEFAULT_SETTINGS = {
    # Hero 昵称
    "hero_name": "Tnine",
    # Hero 个签
    "hero_slogan": "记录代码、生活和探索世界的过程",
    # 统一头像：空表示使用首字母占位（示例：/static/uploads/hero/avatar.png）
    "hero_avatar": "",
    # Hero 背景模式：theme（跟随主题）/ upload（自定义上传）/
    #              auto（自动切换）/ network（网络图库）
    "hero_bg_mode": "theme",
    # 自动切换周期：daily / weekly / random
    "hero_auto_period": "daily",
    # 网络图库来源（占位实现，当前仅支持 unsplash）
    "hero_network_source": "unsplash",
    # 网络图库关键词
    "hero_network_keyword": "minimal",
    # 网络图库更新周期（小时，占位）
    "hero_network_period": "24",
}


def migrate():
    # 1) 建新表（幂等）
    Base.metadata.create_all(bind=engine)
    print("[migrate] 新表创建完成（tags/article_tags/social_links/hero_backgrounds）")

    # 2) 补默认配置
    db = SessionLocal()
    try:
        existing = {
            s.key for s in db.query(Setting).all()
        }
        for key, value in DEFAULT_SETTINGS.items():
            if key in existing:
                continue
            db.add(Setting(
                key=key,
                value=value,
                updated_at=datetime.now(),
            ))
        db.commit()
        print("[migrate] Hero 默认配置已写入 settings 表")
    finally:
        db.close()

    print("[migrate] 迁移完成")


if __name__ == "__main__":
    migrate()
