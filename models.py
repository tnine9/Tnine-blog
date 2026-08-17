from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
)

from sqlalchemy.orm import relationship

from database import Base


# ===========================
# 全站配置（Setting）
# ===========================

class Setting(Base):

    __tablename__ = "settings"


    key = Column(
        String(50),
        primary_key=True
    )


    value = Column(
        String(500),
        default="",
        nullable=False
    )


    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )


# ===========================
# 访客
# ===========================

class Visitor(Base):

    __tablename__ = "visitors"


    visitor_id = Column(
        String(64),
        primary_key=True
    )


    nickname = Column(
        String(50),
        default="匿名访客",
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
# 规则：每次点击 +1，允许重复点赞，不做访客去重
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


    visitor_id = Column(
        String(64),
        default="",
        index=True
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
# 平级评论 + reply_to_id（回复引用，非嵌套）
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


    visitor_id = Column(
        String(64),
        default="",
        index=True
    )


    nickname = Column(
        String(50),
        default="匿名用户"
    )


    content = Column(
        Text,
        nullable=False
    )


    # 被回复评论 ID；NULL 表示普通评论
    reply_to_id = Column(
        Integer,
        ForeignKey(
            "article_comments.id",
            ondelete="SET NULL"
        ),
        nullable=True
    )


    created_at = Column(
        DateTime,
        default=datetime.now
    )


    article = relationship(
        "Article",
        back_populates="comments"
    )


    reply_to = relationship(
        "ArticleComment",
        remote_side=[id]
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


    nickname = Column(
        String(50),
        default="成哥",
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
# 规则：同一访客只能点赞一次，UNIQUE(moment_id, visitor_id)
# ===========================

class MomentLike(Base):

    __tablename__ = "moment_likes"

    __table_args__ = (
        UniqueConstraint(
            "moment_id",
            "visitor_id",
            name="uq_moment_like_visitor"
        ),
    )


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


    visitor_id = Column(
        String(64),
        default="",
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
# 平级评论 + reply_to_id（回复引用，非嵌套）
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


    visitor_id = Column(
        String(64),
        default="",
        index=True
    )


    nickname = Column(
        String(50),
        default="匿名用户"
    )


    content = Column(
        Text,
        nullable=False
    )


    # 被回复评论 ID；NULL 表示普通评论
    reply_to_id = Column(
        Integer,
        ForeignKey(
            "moment_comments.id",
            ondelete="SET NULL"
        ),
        nullable=True
    )


    created_at = Column(
        DateTime,
        default=datetime.now
    )


    moment = relationship(
        "Moment",
        back_populates="comments"
    )


    reply_to = relationship(
        "MomentComment",
        remote_side=[id]
    )



# ===========================
# 留言会话（Thread）
# is_private 属于整个 Thread
# ===========================

class MessageThread(Base):

    __tablename__ = "message_threads"


    id = Column(
        Integer,
        primary_key=True
    )


    visitor_id = Column(
        String(64),
        default="",
        index=True,
        nullable=False
    )


    is_private = Column(
        Boolean,
        default=False,
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


    messages = relationship(
        "Message",
        back_populates="thread",
        cascade="all, delete",
        order_by="Message.created_at"
    )



# ===========================
# 留言消息
# sender_type: visitor / admin
# nickname 保存发送时昵称快照，保证删除 Visitor 后历史展示不丢失
# ===========================

class Message(Base):

    __tablename__ = "message"


    id = Column(
        Integer,
        primary_key=True
    )


    thread_id = Column(
        Integer,
        ForeignKey(
            "message_threads.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )


    sender_type = Column(
        String(20),
        default="visitor",
        nullable=False
    )


    nickname = Column(
        String(50),
        default="匿名访客"
    )


    content = Column(
        Text,
        nullable=False
    )


    created_at = Column(
        DateTime,
        default=datetime.now
    )


    thread = relationship(
        "MessageThread",
        back_populates="messages"
    )
