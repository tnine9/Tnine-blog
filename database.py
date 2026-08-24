# -*- coding: utf-8 -*-
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

import os


# SQLite 数据库文件
# 如果文件不存在，程序第一次运行时会自动创建
# 支持通过环境变量 TNINE_DATABASE_URL 覆盖（用于测试/迁移）
DATABASE_URL = os.environ.get(
    "TNINE_DATABASE_URL",
    "sqlite:///./blog.db",
)


# 创建数据库引擎
# 注意：check_same_thread 仅适用于 SQLite，PostgreSQL 等其它数据库不需要（且不识别该参数）
_engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)


# 创建数据库会话
# 每次需要操作数据库时，通过 SessionLocal() 创建一个会话
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# 所有数据库模型的基类
class Base(DeclarativeBase):
    pass