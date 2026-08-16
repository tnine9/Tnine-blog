from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
)

from sqlalchemy.orm import relationship

from database import Base


# ===========================
# 博客文章
# ===========================

class Article(Base):

    __tablename__ = "articles"


    id = Column(
        Integer,
        primary_key=True
    )


    title = Column(
        String(200),
        nullable=False
    )


    summary = Column(
        String(500),
        nullable=False
    )


    content = Column(
        Text,
        nullable=False
    )


    status = Column(
        String(20),
        default="published",
        nullable=False
    )


    created_at = Column(
        DateTime,
        default=datetime.now
    )


    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )



# ===========================
# 管理员
# ===========================

class Admin(Base):

    __tablename__ = "admins"


    id = Column(
        Integer,
        primary_key=True
    )


    username = Column(
        String(50),
        unique=True,
        nullable=False
    )


    password_hash = Column(
        String(255),
        nullable=False
    )



# ===========================
# 朋友圈
# ===========================

class Moment(Base):

    __tablename__ = "moments"


    id = Column(
        Integer,
        primary_key=True
    )


    nickname = Column(
        String(50),
        default="管理员"
    )


    content = Column(
        Text,
        nullable=False
    )


    created_at = Column(
        DateTime,
        default=datetime.now
    )


    # 图片
    images = relationship(
        "MomentImage",
        back_populates="moment",
        cascade="all, delete"
    )


    # 点赞
    likes = relationship(
        "MomentLike",
        back_populates="moment",
        cascade="all, delete"
    )


    # 评论
    comments = relationship(
        "MomentComment",
        back_populates="moment",
        cascade="all, delete"
    )



# ===========================
# 朋友圈图片
# ===========================

class MomentImage(Base):

    __tablename__ = "moment_images"


    id = Column(
        Integer,
        primary_key=True
    )


    moment_id = Column(
    Integer,
    ForeignKey(
        "moments.id",
        ondelete="CASCADE"
    ),
    nullable=False
    )


    image_path = Column(
        String(255),
        nullable=False
    )


    sort_order = Column(
        Integer,
        default=0
    )


    moment = relationship(
        "Moment",
        back_populates="images"
    )



# ===========================
# 点赞
# ===========================

class MomentLike(Base):

    __tablename__ = "moment_likes"


    id = Column(
        Integer,
        primary_key=True
    )


    moment_id = Column(
    Integer,
    ForeignKey(
        "moments.id",
        ondelete="CASCADE"
    ),
    nullable=False
   )


    nickname = Column(
        String(50),
        default="匿名用户"
    )


    created_at = Column(
        DateTime,
        default=datetime.now
    )


    moment = relationship(
        "Moment",
        back_populates="likes"
    )



# ===========================
# 评论
# ===========================

class MomentComment(Base):

    __tablename__ = "moment_comments"


    id = Column(
        Integer,
        primary_key=True
    )


    moment_id = Column(
    Integer,
    ForeignKey(
        "moments.id",
        ondelete="CASCADE"
    ),
    nullable=False
    )


    nickname = Column(
        String(50),
        default="匿名用户"
    )


    content = Column(
        Text,
        nullable=False
    )


    created_at = Column(
        DateTime,
        default=datetime.now
    )


    moment = relationship(
        "Moment",
        back_populates="comments"
    )

# ===========================
# 留言
# ===========================

class Message(Base):

    __tablename__ = "message"


    id = Column(
        Integer,
        primary_key=True
    )


    nickname = Column(
        String(50),
        default="匿名用户"
    )


    content = Column(
        Text,
        nullable=False
    )


    created_at = Column(
        DateTime,
        default=datetime.now
    )