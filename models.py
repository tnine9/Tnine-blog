# -*- coding: utf-8 -*-
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


    # 首次发布时间（第一次发布时生成，之后修改保持不变；草稿为 NULL）
    published_at = Column(
        DateTime,
        nullable=True
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


    # 标签（多对多）
    tags = relationship(
        "Tag",
        secondary="article_tags",
        back_populates="articles",
    )


    @property
    def like_count(self):
        return len(self.likes)


    @property
    def comment_count(self):
        return len(self.comments)


    @property
    def display_time(self):
        """
        展示时间：已发布文章优先 published_at，草稿退回 created_at。
        """
        return self.published_at or self.created_at



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


    # 昵称：网站核心名称；首次登录后强制完善，可空（空显示"空"）
    nickname = Column(
        String(50),
        default="",
        nullable=True
    )


    # 个人简介（slogan 来源，Hero 首屏展示）
    bio = Column(
        String(200),
        default="",
        nullable=False
    )


    # 管理员收件邮箱（用于接收登录验证码），可空
    email = Column(
        String(255),
        nullable=True
    )


    created_at = Column(
        DateTime,
        default=datetime.now
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


# ===========================
# 标签
# 说明：
# - name 唯一，用于 /tag/{name} 筛选页
# - show_on_home 控制 Hero 首屏胶囊展示
# ===========================

class Tag(Base):

    __tablename__ = "tags"


    id = Column(
        Integer,
        primary_key=True
    )


    name = Column(
        String(50),
        unique=True,
        nullable=False
    )


    description = Column(
        String(200),
        default="",
        nullable=False
    )


    # 是否在首页 Hero 展示
    show_on_home = Column(
        Boolean,
        default=False,
        nullable=False
    )


    # 排序（越小越靠前）
    sort_order = Column(
        Integer,
        default=0,
        nullable=False
    )


    created_at = Column(
        DateTime,
        default=datetime.now
    )


    articles = relationship(
        "Article",
        secondary="article_tags",
        back_populates="tags",
    )



# ===========================
# 文章-标签 关联表
# ===========================

class ArticleTag(Base):

    __tablename__ = "article_tags"

    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "tag_id",
            name="uq_article_tag",
        ),
    )


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


    tag_id = Column(
        Integer,
        ForeignKey(
            "tags.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )



# ===========================
# 社交链接（Hero 底部小图标）
# ===========================

class SocialLink(Base):

    __tablename__ = "social_links"


    id = Column(
        Integer,
        primary_key=True
    )


    name = Column(
        String(50),
        nullable=False
    )


    # 图标类型：github / csdn / wechat / qq / email / link
    icon = Column(
        String(30),
        default="link",
        nullable=False
    )


    # 展示方式：link（链接）/ qrcode（二维码）
    link_type = Column(
        String(30),
        default="link",
        nullable=False
    )


    # 二维码图片路径（link_type=qrcode 时使用）
    qr_code = Column(
        String(500),
        default="",
        nullable=False
    )


    url = Column(
        String(500),
        default="",
        nullable=False
    )


    sort_order = Column(
        Integer,
        default=0,
        nullable=False
    )


    is_visible = Column(
        Boolean,
        default=True,
        nullable=False
    )


    created_at = Column(
        DateTime,
        default=datetime.now
    )



# ===========================
# Hero 背景资源
# 说明：
# - kind：image / video
# - source：upload（自定义上传）/ network（网络图库，占位）
# - is_active：当前选中使用（upload 模式生效）
# - auto 模式从 upload 资源中按周期选取，不使用 is_active
# ===========================

class HeroBackground(Base):

    __tablename__ = "hero_backgrounds"


    id = Column(
        Integer,
        primary_key=True
    )


    kind = Column(
        String(10),
        default="image",
        nullable=False
    )


    source = Column(
        String(20),
        default="upload",
        nullable=False
    )


    file_path = Column(
        String(255),
        default="",
        nullable=False
    )


    title = Column(
        String(100),
        default="",
        nullable=False
    )


    sort_order = Column(
        Integer,
        default=0,
        nullable=False
    )


    is_active = Column(
        Boolean,
        default=False,
        nullable=False
    )


    created_at = Column(
        DateTime,
        default=datetime.now
    )
# ===========================# ֪ͨ# type: article_like / article_comment / moment_like / moment_comment / message / message_reply / visitor# target_id: 目标对象 ID（文章/朋友圈/留言会话/访客），用于跳转# ===========================class Notification(Base):    __tablename__ = "notifications"    id = Column(        Integer,        primary_key=True    )    type = Column(        String(30),        default="",        nullable=False,        index=True    )    target_id = Column(        Integer,        default=0,        nullable=False    )    content = Column(        String(500),        default="",        nullable=False    )    is_read = Column(        Boolean,        default=False,        nullable=False    )    created_at = Column(        DateTime,        default=datetime.now    )


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, nullable=True)

    type = Column(String(50))

    content = Column(Text)

    is_read = Column(Boolean, default=False)

    created_at = Column(
        DateTime,
        default=datetime.now
    )