# -*- coding: utf-8 -*-
"""
通知系统独立 Service（Tnine v2）

类型：article_like / article_comment / moment_like / moment_comment /
      message / message_reply / visitor

跳转逻辑（前端根据 type 拼 URL）：
- article_like / article_comment  → /article/{target_id}
- moment_like / moment_comment    → /moment/{target_id}
- message / message_reply         → /message/{target_id}
- visitor                         → /admin/visitors
"""

NOTIFICATION_TYPES = {
    "article_like",
    "article_comment",
    "moment_like",
    "moment_comment",
    "message",
    "message_reply",
    "visitor",
}

NOTIFICATION_TYPE_LABELS = {
    "article_like": "文章点赞",
    "article_comment": "文章评论",
    "moment_like": "朋友圈点赞",
    "moment_comment": "朋友圈评论",
    "message": "新留言",
    "message_reply": "留言回复",
    "visitor": "新访客",
}


def create_notification(
    db,
    type: str,
    target_id: int,
    content: str,
):
    """
    写入一条通知。content 应包含互动者昵称与摘要，便于后台直接展示。
    """

    if type not in NOTIFICATION_TYPES:
        return None

    from models import Notification

    notification = Notification(
        type=type,
        target_id=int(target_id or 0),
        content=(content or "")[:500],
        is_read=False,
    )

    db.add(notification)

    # 不主动 commit，由调用方统一提交
    db.flush()

    return notification


def get_unread_count(db):
    from models import Notification

    return (
        db.query(Notification)
        .filter(Notification.is_read == False)  # noqa: E712
        .count()
    )


def get_latest_notifications(db, limit: int = 5):
    from models import Notification

    return (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


def list_notifications(db, limit: int = 100, unread_only: bool = False):
    from models import Notification

    query = db.query(Notification)

    if unread_only:
        query = query.filter(Notification.is_read == False)  # noqa: E712

    return (
        query.order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


def mark_notification_read(db, notification_id: int):
    from models import Notification

    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id)
        .first()
    )

    if notification is None:
        return False

    notification.is_read = True

    db.commit()

    return True


def mark_all_notifications_read(db):
    from models import Notification

    unread = (
        db.query(Notification)
        .filter(Notification.is_read == False)  # noqa: E712
        .update(
            {
                Notification.is_read: True,
            }
        )
    )

    db.commit()

    return unread
