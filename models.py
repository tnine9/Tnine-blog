from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
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


    # 浏览次数
    views = Column(
        Integer,
        default=0,
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


    # 点赞
    likes = relationship(
        "ArticleLike",
        back_populates="article",
        cascade="all, delete"
    )


    # 评论
    comments = relationship(
        "ArticleComment",
        back_populates="article",
        cascade="all, delete"
    )


    @property
    def like_count(self):
        return len(self.likes)


    @property
    def comment_count(self):
        return len(self.comments)



# ===========================
# 文章点赞
# ===========================

class ArticleLike(Base):

    __tablename__ = "article_likes"


    id = Column(
        Integer,
        primary_key=True
    )


    article_id = Column(
        Integer,
        ForeignKey(
            "articles.id",
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


    article = relationship(
        "Article",
        back_populates="likes"
    )



# ===========================
# 文章评论
# ===========================

class ArticleComment(Base):

    __tablename__ = "article_comments"


    id = Column(
        Integer,
        primary_key=True
    )


    article_id = Column(
        Integer,
        ForeignKey(
            "articles.id",
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


    article = relationship(
        "Article",
        back_populates="comments"
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


    @property
    def like_count(self):
        return len(self.likes)


    @property
    def comment_count(self):
        return len(self.comments)



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
# 朋友圈点赞
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
# 朋友圈评论
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


    # 是否私密（仅管理员可见）
    is_private = Column(
        Boolean,
        default=False,
        nullable=False
    )


    # 发布者标识（访客 cookie 中的访客 ID）
    # 用于识别"发布者本人"以允许其回复
    visitor_id = Column(
        String(64),
        default=""
    )


    # 回复父留言 ID（NULL 表示顶层留言）
    parent_id = Column(
        Integer,
        ForeignKey(
            "message.id",
            ondelete="CASCADE"
        ),
        nullable=True
    )


    created_at = Column(
        DateTime,
        default=datetime.now
    )


    # 该留言下的回复
    replies = relationship(
        "Message",
        back_populates="parent",
        cascade="all, delete",
        order_by="Message.created_at"
    )


    parent = relationship(
        "Message",
        back_populates="replies",
        remote_side=[id]
    )
