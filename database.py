from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# SQLite 数据库文件
# 如果文件不存在，程序第一次运行时会自动创建
DATABASE_URL = "sqlite:///./blog.db"


# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False
    },
)


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