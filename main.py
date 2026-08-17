from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pwdlib import PasswordHash
import markdown
import nh3
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from database import SessionLocal, Base, engine
from models import (
    Article,
    ArticleLike,
    ArticleComment,
    Admin,
    Setting,
    Moment,
    MomentImage,
    MomentLike,
    MomentComment,
    Message,
    MessageThread,
    Visitor,
)

from fastapi import UploadFile, File
import os
import shutil
import uuid
from datetime import datetime


# ============================================================
# 数据库初始化
# ============================================================

Base.metadata.create_all(bind=engine)


# ============================================================
# FastAPI
# ============================================================

app = FastAPI()


# ============================================================
# Session
# ============================================================

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get(
        "TNINE_SECRET_KEY",
        "Tnine-dev-secret-2026",
    ),
)


# ============================================================
# 密码
# ============================================================

password_hasher = PasswordHash.recommended()


# ============================================================
# 管理员初始化
# 需求：固定账号 admin，取消注册页
# 若 admins 表为空且设置了 TNINE_ADMIN_INITIAL_PASSWORD，
# 启动时自动创建初始管理员（昵称默认"成哥"）
# ============================================================

def ensure_initial_admin():
    db = SessionLocal()
    try:
        admin_count = db.query(Admin).count()
        if admin_count > 0:
            return
        initial_password = os.environ.get(
            "TNINE_ADMIN_INITIAL_PASSWORD"
        )
        if not initial_password:
            return
        if len(initial_password) < 6:
            print(
                "[Tnine] TNINE_ADMIN_INITIAL_PASSWORD 至少 6 位，"
                "跳过初始管理员创建"
            )
            return
        admin = Admin(
            username="admin",
            password_hash=password_hasher.hash(
                initial_password
            ),
            nickname="成哥",
        )
        db.add(admin)
        db.commit()
        print(
            "[Tnine] 已通过环境变量创建初始管理员 admin"
        )
    finally:
        db.close()


ensure_initial_admin()


# ============================================================
# 权限
# ============================================================

def get_current_admin(request: Request):
    return request.session.get("admin_id")


def require_admin(request: Request):
    return get_current_admin(request)


def is_admin(request: Request):
    return get_current_admin(request) is not None


# ============================================================
# 全站主题
# 需求：
# - 主题为全站设置（存 Setting 表），已选主题对所有访客生效
# - 仅管理员可切换主题，访客无权切换
# ============================================================

SITE_THEME_KEY = "site_theme"

VALID_THEMES = ("light", "dark")


def get_site_theme():
    """
    读取全站主题，默认 light。
    """

    db = SessionLocal()

    try:

        setting = (
            db.query(Setting)
            .filter(Setting.key == SITE_THEME_KEY)
            .first()
        )

        if (
            setting
            and setting.value in VALID_THEMES
        ):

            return setting.value

        return "light"

    finally:

        db.close()


def set_site_theme(theme: str):
    """
    写入全站主题（仅管理员调用）。
    """

    if theme not in VALID_THEMES:

        return False

    db = SessionLocal()

    try:

        setting = (
            db.query(Setting)
            .filter(Setting.key == SITE_THEME_KEY)
            .first()
        )

        if setting is None:

            setting = Setting(
                key=SITE_THEME_KEY,
                value=theme,
            )

            db.add(setting)

        else:

            setting.value = theme

        db.commit()

        return True

    finally:

        db.close()


def get_common_context(request: Request):
    return {
        "is_admin": is_admin(request),
        "admin_username": request.session.get(
            "admin_username"
        ),
        "admin_nickname": request.session.get(
            "admin_nickname",
            "成哥",
        ),
        "visitor_id": get_visitor_id(request),
        "theme": get_site_theme(),
    }


# ============================================================
# 访客身份
# 需求：
# - visitor_id：UUID Cookie，365 天，HttpOnly，SameSite=Lax
# - 昵称首次设置机制保留（nickname_modal）
# - 访客身份与管理员身份分离
# ============================================================

VISITOR_NICKNAME_COOKIE = "tnine_nickname"

VISITOR_ID_COOKIE = "tnine_visitor_id"

ANONYMOUS_GUEST_NAME = "匿名访客"

# 生产环境（HTTPS）下开启 Secure Cookie
SECURE_COOKIES = (
    os.environ.get("TNINE_ENV") == "production"
)

# 访客 ID Cookie 有效期：365 天
VISITOR_ID_MAX_AGE = 60 * 60 * 24 * 365


def get_visitor_nickname(request: Request):
    """
    获取游客昵称 Cookie。

    返回：
    - 有昵称：昵称
    - 没有：None
    """

    return request.cookies.get(
        VISITOR_NICKNAME_COOKIE
    )


def get_visitor_id(request: Request):
    """
    获取访客唯一标识 Cookie。

    没有则生成一个新的并返回（由调用方决定是否写回 Cookie）。
    """

    visitor_id = request.cookies.get(
        VISITOR_ID_COOKIE
    )

    if visitor_id:
        return visitor_id

    return uuid.uuid4().hex


def set_visitor_id_cookie(
    response,
    visitor_id: str,
):
    """
    把访客 ID 写入响应 Cookie（365 天）。
    """

    response.set_cookie(
        key=VISITOR_ID_COOKIE,
        value=visitor_id,
        max_age=VISITOR_ID_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=SECURE_COOKIES,
        path="/",
    )


def ensure_visitor(
    db,
    visitor_id: str,
    nickname: str | None = None,
):
    """
    确保 Visitor 档案存在（首次互动时自动建档）。

    已存在则更新昵称快照与最后活动时间。
    """

    if not visitor_id:
        return None

    visitor = (
        db.query(Visitor)
        .filter(
            Visitor.visitor_id == visitor_id
        )
        .first()
    )

    if visitor is None:

        visitor = Visitor(
            visitor_id=visitor_id,
            nickname=(
                (nickname or "").strip()[:50]
                or ANONYMOUS_GUEST_NAME
            ),
        )

        db.add(visitor)

    else:

        # 管理员身份互动时昵称快照用管理员昵称，
        # 但不覆盖访客自己设置的昵称
        visitor.updated_at = datetime.now()

    return visitor


def get_actor_identity(
    request: Request,
    fallback_nickname: str | None = None,
):
    """
    获取当前互动用户身份。

    返回 (display_name, visitor_id)：
    - display_name：展示昵称（管理员返回管理员昵称，访客返回昵称）
    - visitor_id：浏览器访客 ID（管理员也拥有，用于互动数据归属）

    访客没有昵称时 display_name 为 None（需要先设置昵称）。
    """

    visitor_id = get_visitor_id(request)

    # 管理员：使用管理员昵称（成哥）
    if is_admin(request):

        nickname = request.session.get(
            "admin_nickname",
            "成哥",
        )

        return nickname, visitor_id

    # 本次操作明确指定昵称
    if fallback_nickname is not None:

        nickname = fallback_nickname.strip()

        if nickname:

            return nickname[:50], visitor_id

        return None, visitor_id

    # Cookie 昵称
    nickname = get_visitor_nickname(request)

    if nickname:

        return nickname.strip()[:50], visitor_id

    return None, visitor_id


def get_liked_moment_ids(
    db,
    visitor_id: str,
):
    """
    查询当前访客已点赞的朋友圈 ID 列表。
    """

    if not visitor_id:
        return []

    rows = (
        db.query(MomentLike.moment_id)
        .filter(
            MomentLike.visitor_id == visitor_id
        )
        .all()
    )

    return [r[0] for r in rows]


# ============================================================
# 访客 ID 中间件
# 首次访问任意页面即签发 365 天访客 Cookie
# ============================================================

@app.middleware("http")
async def ensure_visitor_id_middleware(request: Request, call_next):
    response = await call_next(request)
    if not request.cookies.get(VISITOR_ID_COOKIE):
        visitor_id = uuid.uuid4().hex
        set_visitor_id_cookie(response, visitor_id)
    return response


# ============================================================
# 静态文件
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


templates = Jinja2Templates(
    directory="templates"
)

# ============================================================
# 朋友圈图片上传目录
# ============================================================

MOMENT_IMAGE_DIR = "static/uploads/moments"


if not os.path.exists(MOMENT_IMAGE_DIR):
    os.makedirs(MOMENT_IMAGE_DIR)


# ============================================================
# PUBLIC：博客首页
# ============================================================

@app.get("/")
def home(request: Request):

    db = SessionLocal()

    try:

        # ==========================
        # 获取文章
        # ==========================

        articles = (
            db.query(Article)
            .filter(
                Article.status == "published"
            )
            .options(
                selectinload(Article.likes),
                selectinload(Article.comments).selectinload(ArticleComment.reply_to),
            )
            .order_by(
                Article.created_at.desc()
            )
            .all()
        )


        # ==========================
        # 获取朋友圈
        # ==========================

        moments = (
            db.query(Moment)
            .options(
               selectinload(Moment.images),
               selectinload(Moment.likes),
               selectinload(Moment.comments).selectinload(MomentComment.reply_to),
            )
            .order_by(
               Moment.created_at.desc()
            )
            .all()
        )


        # ==========================
        # 获取留言（按身份可见性过滤）
        # 公开留言所有人可见；私密留言仅发布者本人与管理员可见
        # ==========================

        visitor_id = get_visitor_id(request)

        is_admin_flag = is_admin(request)

        message_threads = (
            db.query(MessageThread)
            .options(
                selectinload(MessageThread.messages),
            )
            .order_by(
                MessageThread.updated_at.desc()
            )
            .all()
        )

        visible_threads = []

        for thread in message_threads:

            if (
                thread.is_private
                and not is_admin_flag
                and thread.visitor_id != visitor_id
            ):

                continue

            visible_threads.append(thread)


        # ==========================
        # 合并时间线
        # ==========================

        timeline = []


        for article in articles:

            timeline.append(
                {
                    "type": "article",
                    "data": article,
                }
            )


        for moment in moments:

            timeline.append(
                {
                    "type": "moment",
                    "data": moment,
                }
            )


        for thread in visible_threads:

            timeline.append(
                {
                    "type": "message",
                    "data": thread,
                }
            )


        # 按时间倒序

        timeline.sort(
            key=lambda x: x["data"].created_at,
            reverse=True
        )


        context = get_common_context(request)

        context["timeline"] = timeline

        context["threads"] = visible_threads

        context["liked_moment_ids"] = get_liked_moment_ids(
            db,
            get_visitor_id(request),
        )


        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=context,
        )


    finally:

        db.close()


# ============================================================
# PUBLIC：文章详情
# ============================================================
@app.get("/article/{article_id}")
def article_detail(
    request: Request,
    article_id: int,
):

    db = SessionLocal()

    try:

        article = (
            db.query(Article)
            .options(
                selectinload(Article.likes),
                selectinload(Article.comments).selectinload(ArticleComment.reply_to),
            )
            .filter(
                Article.id == article_id
            )
            .first()
        )

        if article is None:
            raise HTTPException(
                status_code=404,
                detail="文章不存在",
            )


        # ====================================================
        # 草稿保护
        # ====================================================

        # 非管理员不能查看草稿
        if (
            article.status != "published"
            and not is_admin(request)
        ):
            raise HTTPException(
                status_code=404,
                detail="文章不存在",
            )


        # ====================================================
        # 浏览计数 +1（已发布文章）
        # ====================================================

        if article.status == "published":

            article.views = (
                article.views or 0
            ) + 1

            db.commit()


        # Markdown → HTML（nh3 清洗，防文章内容注入 XSS）
        # 保留 a/img/h1-h4(code/pre class) 等常用属性，
        # 其中 id 供 toc 目录锚点跳转使用
        article_html = nh3.clean(
            markdown.markdown(
                article.content,
                extensions=[
                    "fenced_code",
                    "tables",
                    "toc",
                ],
            ),
            tags={
                "a", "img", "h1", "h2", "h3", "h4",
                "p", "br", "hr", "ul", "ol", "li",
                "strong", "em", "code", "pre", "blockquote",
                "table", "thead", "tbody", "tr", "th", "td",
                "span", "div", "input",
            },
            attributes={
                "a": {"href", "title", "target", "rel"},
                "img": {"src", "alt", "title", "width", "height"},
                "code": {"class"},
                "pre": {"class"},
                "h1": {"id"},
                "h2": {"id"},
                "h3": {"id"},
                "h4": {"id"},
                "span": {"class"},
                "div": {"class"},
                "input": {"type", "checked", "disabled"},
                "table": {"class"},
                "th": {"align"},
                "td": {"align"},
            },
            url_schemes={
                "http", "https", "mailto",
                "tel", "data",
            },
            link_rel=None,
        )

        # 生成目录（toc 扩展会注入 div.toc，这里只取标题锚点）
        toc_html = ""
        if hasattr(article, "toc_html"):
            toc_html = article.toc_html

        context = get_common_context(request)

        context["article"] = article

        context["article_html"] = article_html

        context["liked_moment_ids"] = []

        return templates.TemplateResponse(
            request=request,
            name="article_detail.html",
            context=context,
        )


    finally:

        db.close()


# ============================================================
# GUEST：管理员登录页
# ============================================================

@app.get("/admin/login")
def admin_login_page(
    request: Request,
):

    # 已经登录
    if not is_admin(request):

        db = SessionLocal()

        try:

            admin_count = (
                db.query(Admin)
                .count()
            )

            context = get_common_context(request)

            context["error"] = None

            context["need_initial_password"] = (
                admin_count == 0
            )

            return templates.TemplateResponse(
                request=request,
                name="admin_login.html",
                context=context,
            )

        finally:

            db.close()

    return RedirectResponse(
        url="/admin",
        status_code=303,
    )


# ============================================================
# GUEST：管理员登录
# ============================================================

@app.post("/admin/login")
def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):

    if not is_admin(request):

        username = username.strip()

        db = SessionLocal()

        try:

            admin = (
                db.query(Admin)
                .filter(
                    Admin.username == username
                )
                .first()
            )

            if admin is None:

                context = get_common_context(request)

                context["error"] = "用户名或密码错误"

                return templates.TemplateResponse(
                    request=request,
                    name="admin_login.html",
                    context=context,
                )

            password_valid = (
                password_hasher.verify(
                    password,
                    admin.password_hash,
                )
            )

            if not password_valid:

                context = get_common_context(request)

                context["error"] = "用户名或密码错误"

                return templates.TemplateResponse(
                    request=request,
                    name="admin_login.html",
                    context=context,
                )

            request.session["admin_id"] = admin.id

            request.session[
                "admin_username"
            ] = admin.username

            request.session[
                "admin_nickname"
            ] = admin.nickname or "成哥"

            return RedirectResponse(
                url="/admin",
                status_code=303,
            )

        finally:

            db.close()

    return RedirectResponse(
        url="/admin",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：管理员主页
# ============================================================

@app.get("/admin")
def admin_home(
    request: Request,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        # 管理员可以看到草稿
        articles = (
            db.query(Article)
            .order_by(
                Article.created_at.desc()
            )
            .all()
        )


        context = get_common_context(request)

        context["articles"] = articles

        context["article_count"] = len(
            articles
        )

        # 访客数量与留言会话数
        context["visitor_count"] = (
            db.query(Visitor)
            .count()
        )

        context["thread_count"] = (
            db.query(MessageThread)
            .count()
        )


        return templates.TemplateResponse(
            request=request,
            name="admin_home.html",
            context=context,
        )

    finally:
        db.close()


# ============================================================
# AUTHENTICATED：管理员个人资料（修改昵称）
# ============================================================

@app.get("/admin/profile")
def admin_profile_page(
    request: Request,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        admin = (
            db.query(Admin)
            .filter(
                Admin.id == request.session["admin_id"]
            )
            .first()
        )

        if admin is None:

            return RedirectResponse(
                url="/admin/login",
                status_code=303,
            )


        context = get_common_context(request)

        context["admin"] = admin

        context["error"] = None

        return templates.TemplateResponse(
            request=request,
            name="admin_profile.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：保存管理员昵称
# ============================================================

@app.post("/admin/profile")
def admin_profile_save(
    request: Request,
    nickname: str = Form(""),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        admin = (
            db.query(Admin)
            .filter(
                Admin.id == request.session["admin_id"]
            )
            .first()
        )

        if admin is None:

            return RedirectResponse(
                url="/admin/login",
                status_code=303,
            )

        nickname = nickname.strip()[:50]

        if not nickname:

            context = get_common_context(request)

            context["admin"] = admin

            context["error"] = "昵称不能为空"

            return templates.TemplateResponse(
                request=request,
                name="admin_profile.html",
                context=context,
            )

        admin.nickname = nickname

        db.commit()

        # 同步会话昵称
        request.session["admin_nickname"] = nickname

        return RedirectResponse(
            url="/admin/profile",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：访客管理
# ============================================================

@app.get("/admin/visitors")
def admin_visitors(
    request: Request,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        visitors = (
            db.query(Visitor)
            .order_by(
                Visitor.updated_at.desc()
            )
            .all()
        )

        # 每个访客的互动统计
        visitor_stats = []

        for visitor in visitors:

            vid = visitor.visitor_id

            article_likes = (
                db.query(ArticleLike)
                .filter(ArticleLike.visitor_id == vid)
                .count()
            )

            moment_likes = (
                db.query(MomentLike)
                .filter(MomentLike.visitor_id == vid)
                .count()
            )

            article_comments = (
                db.query(ArticleComment)
                .filter(ArticleComment.visitor_id == vid)
                .count()
            )

            moment_comments = (
                db.query(MomentComment)
                .filter(MomentComment.visitor_id == vid)
                .count()
            )

            threads = (
                db.query(MessageThread)
                .filter(MessageThread.visitor_id == vid)
                .count()
            )

            visitor_stats.append(
                {
                    "visitor": visitor,
                    "interaction_count": (
                        article_likes
                        + moment_likes
                        + article_comments
                        + moment_comments
                        + threads
                    ),
                    "detail": {
                        "article_likes": article_likes,
                        "moment_likes": moment_likes,
                        "article_comments": article_comments,
                        "moment_comments": moment_comments,
                        "threads": threads,
                    },
                }
            )

        context = get_common_context(request)

        context["visitor_stats"] = visitor_stats

        return templates.TemplateResponse(
            request=request,
            name="admin_visitors.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：删除访客档案
# 需求：只删 Visitor 档案，不删历史互动（评论/点赞/留言保留）
# ============================================================

@app.post("/admin/visitors/{visitor_id}/delete")
def admin_delete_visitor(
    request: Request,
    visitor_id: str,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        visitor = (
            db.query(Visitor)
            .filter(
                Visitor.visitor_id == visitor_id
            )
            .first()
        )

        if visitor is not None:

            db.delete(visitor)

            db.commit()

        return RedirectResponse(
            url="/admin/visitors",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：新建文章页面
# ============================================================

@app.get("/admin/new")
def new_article_page(
    request: Request,
):
    """
    新建文章页面。

    使用统一编辑器：
    article = None
    """

    if require_admin(request) is None:
        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    context = get_common_context(request)

    context["article"] = None

    return templates.TemplateResponse(
        request=request,
        name="admin_editor.html",
        context=context,
    )


# ============================================================
# AUTHENTICATED：新建文章
# ============================================================

@app.post("/admin/new")
def create_article(
    request: Request,
    title: str = Form(...),
    summary: str = Form(...),
    content: str = Form(...),
    action: str = Form("publish"),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    # ========================================================
    # 判断保存方式
    # ========================================================

    if action == "draft":
        status = "draft"
    else:
        status = "published"


    db = SessionLocal()

    try:

        article = Article(
            title=(title or "").strip() or "无标题",
            summary=(summary or "").strip(),
            content=content,
            status=status,
        )

        db.add(article)

        db.commit()

        db.refresh(article)


        # ====================================================
        # 草稿
        # ====================================================

        if status == "draft":

            return RedirectResponse(
                url=f"/admin/edit/{article.id}",
                status_code=303,
            )


        # ====================================================
        # 正式发布
        # ====================================================

        return RedirectResponse(
            url=f"/article/{article.id}",
            status_code=303,
        )

    finally:
        db.close()


# ============================================================
# AUTHENTICATED：编辑页面
# ============================================================

@app.get("/admin/edit/{article_id}")
def edit_article_page(
    request: Request,
    article_id: int,
):
    """
    编辑文章页面。

    使用统一编辑器：
    article = 已有文章
    """

    if require_admin(request) is None:
        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        article = (
            db.query(Article)
            .filter(
                Article.id == article_id
            )
            .first()
        )

        if article is None:
            return RedirectResponse(
                url="/admin",
                status_code=303,
            )

        context = get_common_context(request)

        context["article"] = article

        return templates.TemplateResponse(
            request=request,
            name="admin_editor.html",
            context=context,
        )

    finally:
        db.close()


# ============================================================
# AUTHENTICATED：保存编辑
# ============================================================

@app.post("/admin/edit/{article_id}")
def update_article(
    request: Request,
    article_id: int,
    title: str = Form(...),
    summary: str = Form(...),
    content: str = Form(...),
    action: str = Form("publish"),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        article = (
            db.query(Article)
            .filter(
                Article.id == article_id
            )
            .first()
        )


        if article is None:

            return RedirectResponse(
                url="/admin",
                status_code=303,
            )


        # 更新正文
        article.title = (title or "").strip() or "无标题"
        article.summary = (summary or "").strip()
        article.content = content


        # ====================================================
        # 保存草稿
        # ====================================================

        if action == "draft":

            article.status = "draft"

            db.commit()

            db.refresh(article)


            return RedirectResponse(
                url=f"/admin/edit/{article.id}",
                status_code=303,
            )


        # ====================================================
        # 发布
        # ====================================================

        article.status = "published"

        # 发布又编辑：发布时间更新为本次修改时间
        article.created_at = datetime.now()

        db.commit()

        db.refresh(article)


        return RedirectResponse(
            url=f"/article/{article.id}",
            status_code=303,
        )

    finally:
        db.close()


# ============================================================
# AUTHENTICATED：删除文章
# ============================================================

@app.post("/admin/delete/{article_id}")
def delete_article(
    request: Request,
    article_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        article = (
            db.query(Article)
            .filter(
                Article.id == article_id
            )
            .first()
        )


        if article is None:

            return RedirectResponse(
                url="/admin",
                status_code=303,
            )


        db.delete(article)

        db.commit()


        return RedirectResponse(
            url="/admin",
            status_code=303,
        )

    finally:
        db.close()


# ============================================================
# AUTHENTICATED：退出登录
# ============================================================

@app.get("/admin/logout")
def admin_logout(
    request: Request,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    request.session.clear()


    return RedirectResponse(
        url="/admin/login",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：切换全站主题
# 仅管理员可切换；已选主题全站生效（存 Setting 表）
# ============================================================

@app.post("/admin/theme")
def admin_set_theme(
    request: Request,
    theme: str = Form(...),
):

    if require_admin(request) is None:

        return JSONResponse(
            status_code=403,
            content={"ok": False, "detail": "无权操作"},
        )


    if theme not in VALID_THEMES:

        return JSONResponse(
            status_code=400,
            content={"ok": False, "detail": "无效主题"},
        )


    set_site_theme(theme)


    return JSONResponse(
        content={"ok": True, "theme": theme},
    )


# ============================================================
# AUTHENTICATED：发布朋友圈页面
# ============================================================

@app.get("/admin/moment/new")
def new_moment_page(
    request: Request,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    context = get_common_context(request)


    return templates.TemplateResponse(
        request=request,
        name="moment_editor.html",
        context=context,
    )



# ============================================================
# AUTHENTICATED：发布朋友圈
# ============================================================

@app.post("/admin/moment/create")
def create_moment(
    request: Request,
    content: str = Form(...),
    images: list[UploadFile] | None = File(None),
):


    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()


    try:


        moment = Moment(
            nickname=request.session.get(
                "admin_nickname",
                "成哥",
            ),
            content=content,
        )


        db.add(moment)

        db.commit()

        db.refresh(moment)



        # 保存图片

        # 最多9张

        images = images or []
        images = images[:9]


        for index, image in enumerate(images):


            if image.filename:
                # 清理文件名，防止路径穿透
                original_name = os.path.basename(
                    image.filename
                )

                # 仅允许常见图片格式
                if original_name.lower().split(".")[-1] not in (
                    "jpg",
                    "jpeg",
                    "png",
                    "gif",
                    "webp",
                    "bmp",
                ):
                    continue

                # MIME 校验：伪造扩展名的文件会被拒绝
                if not (
                    image.content_type
                    and image.content_type.startswith("image/")
                ):
                    continue

                # 单张图片大小限制 10MB，防止磁盘被大文件耗尽
                image.file.seek(0, 2)

                file_size = image.file.tell()

                image.file.seek(0)

                if file_size > 10 * 1024 * 1024:
                    continue

                filename = (
                    f"{moment.id}_"
                    f"{uuid.uuid4().hex}_"
                    f"{original_name}"
)


                save_path = os.path.join(
                    MOMENT_IMAGE_DIR,
                    filename
                )


                with open(
                    save_path,
                    "wb"
                ) as buffer:

                    shutil.copyfileobj(
                        image.file,
                        buffer
                    )


                moment_image = MomentImage(

                    moment_id=moment.id,

                    image_path=(
                        "/static/uploads/moments/"
                        + filename
                    ),

                    sort_order=index
                )


                db.add(moment_image)



        db.commit()



        return RedirectResponse(
            url="/",
            status_code=303,
        )


    finally:

        db.close()


# ============================================================
# PUBLIC：保存访客昵称
# ============================================================

@app.post("/nickname")
def save_visitor_nickname(
    request: Request,
    nickname: str = Form(""),
):
    """
    保存游客昵称。

    输入昵称：
        保存 365 天 Cookie

    留空：
        删除昵称 Cookie
    """

    nickname = nickname.strip()[:50]


    response = JSONResponse(
        {
            "success": True,
            "nickname": nickname,
        }
    )


    # 有昵称
    if nickname:

        response.set_cookie(
            key=VISITOR_NICKNAME_COOKIE,
            value=nickname,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
            secure=SECURE_COOKIES,
            path="/",
        )

    else:

        response.delete_cookie(
            key=VISITOR_NICKNAME_COOKIE,
            path="/",
        )


    # 同步访客档案昵称
    visitor_id = get_visitor_id(request)

    if visitor_id:

        db = SessionLocal()

        try:

            ensure_visitor(db, visitor_id, nickname)

            db.commit()

        finally:

            db.close()


    set_visitor_id_cookie(response, visitor_id)

    return response


# ============================================================
# PUBLIC：朋友圈点赞 / 取消点赞
# 需求：同一访客仅可点赞一次，UNIQUE(moment_id, visitor_id)
# ============================================================

@app.post("/moment/{moment_id}/like")
def like_moment(
    request: Request,
    moment_id: int,
    nickname: str | None = Form(None),
):
    db = SessionLocal()

    try:

        moment = (
            db.query(Moment)
            .filter(
                Moment.id == moment_id
            )
            .first()
        )


        if moment is None:

            return JSONResponse(
                {
                    "success": False,
                    "error": "朋友圈不存在",
                },
                status_code=404,
            )


        # ====================================================
        # 获取当前身份
        # ====================================================

        actor_name, visitor_id = get_actor_identity(
            request,
            nickname,
        )


        # 没有昵称
        if not actor_name:

            return JSONResponse(
                {
                    "success": False,
                    "nickname_required": True,
                },
                status_code=401,
            )


        # ====================================================
        # 访客档案建档
        # ====================================================

        ensure_visitor(db, visitor_id, actor_name)

        db.flush()


        # ====================================================
        # 查询当前访客是否已经点赞（按 visitor_id）
        # ====================================================

        existing_like = (
            db.query(MomentLike)
            .filter(
                MomentLike.moment_id == moment_id,
                MomentLike.visitor_id == visitor_id,
            )
            .first()
        )


        # ====================================================
        # 已点赞 → 保持点赞（不支持取消）
        # ====================================================

        if existing_like:

            db.commit()

            like_count = (
                db.query(MomentLike)
                .filter(
                    MomentLike.moment_id == moment_id
                )
                .count()
            )

            return JSONResponse(
                {
                    "success": True,
                    "liked": True,
                    "already_liked": True,
                    "like_count": like_count,
                    "nickname": actor_name,
                }
            )


        # ====================================================
        # 未点赞 → 新增
        # ====================================================

        like = MomentLike(
            moment_id=moment_id,
            visitor_id=visitor_id,
            nickname=actor_name,
        )

        db.add(like)

        liked = True


        db.commit()


        # ====================================================
        # 重新统计
        # ====================================================

        like_count = (
            db.query(MomentLike)
            .filter(
                MomentLike.moment_id == moment_id
            )
            .count()
        )


        return JSONResponse(
            {
                "success": True,
                "liked": liked,
                "like_count": like_count,
                "nickname": actor_name,
            }
        )


    finally:

        db.close()


# ============================================================
# PUBLIC：朋友圈评论
# 需求：平级评论 + reply_to_id（回复引用）
# ============================================================

@app.post("/moment/{moment_id}/comment")
def comment_moment(
    request: Request,
    moment_id: int,
    content: str = Form(...),
    nickname: str | None = Form(None),
    reply_to_id: int | None = Form(None),
):
    db = SessionLocal()

    try:

        moment = (
            db.query(Moment)
            .filter(
                Moment.id == moment_id
            )
            .first()
        )


        if moment is None:

            return JSONResponse(
                {
                    "success": False,
                    "error": "朋友圈不存在",
                },
                status_code=404,
            )


        content = content.strip()


        if not content:

            return JSONResponse(
                {
                    "success": False,
                    "error": "评论内容不能为空",
                },
                status_code=400,
            )


        if len(content) > 1000:

            return JSONResponse(
                {
                    "success": False,
                    "error": "评论不能超过 1000 个字符",
                },
                status_code=400,
            )


        # ====================================================
        # 获取当前身份
        # ====================================================

        actor_name, visitor_id = get_actor_identity(
            request,
            nickname,
        )


        if not actor_name:

            return JSONResponse(
                {
                    "success": False,
                    "nickname_required": True,
                },
                status_code=401,
            )


        # ====================================================
        # 校验回复引用（可选）
        # ====================================================

        if reply_to_id is not None:

            reply_target = (
                db.query(MomentComment)
                .filter(
                    MomentComment.id == reply_to_id,
                    MomentComment.moment_id == moment_id,
                )
                .first()
            )

            if reply_target is None:

                return JSONResponse(
                    {
                        "success": False,
                        "error": "回复的评论不存在",
                    },
                    status_code=400,
                )


        # ====================================================
        # 访客档案建档
        # ====================================================

        ensure_visitor(db, visitor_id, actor_name)

        db.flush()


        # ====================================================
        # 保存评论
        # ====================================================

        comment = MomentComment(
            moment_id=moment.id,
            visitor_id=visitor_id,
            nickname=actor_name,
            content=content,
            reply_to_id=reply_to_id,
        )


        db.add(comment)

        db.commit()

        db.refresh(comment)


        comment_count = (
            db.query(MomentComment)
            .filter(
                MomentComment.moment_id == moment_id
            )
            .count()
        )


        reply_to_nickname = None

        if (
            reply_to_id is not None
            and reply_target is not None
        ):

            reply_to_nickname = reply_target.nickname


        return JSONResponse(
            {
                "success": True,
                "comment_id": comment.id,
                "nickname": actor_name,
                "content": comment.content,
                "comment_count": comment_count,
                "reply_to_id": reply_to_id,
                "reply_to_nickname": reply_to_nickname,
                "created_at": comment.created_at.strftime("%Y-%m-%d %H:%M"),
            }
        )


    finally:

        db.close()


# ============================================================
# PUBLIC：文章点赞
# 需求：每次点击 +1，允许重复点赞，不做访客去重
# ============================================================

@app.post("/article/{article_id}/like")
def like_article(
    request: Request,
    article_id: int,
    nickname: str | None = Form(None),
):
    db = SessionLocal()

    try:

        article = (
            db.query(Article)
            .filter(
                Article.id == article_id
            )
            .first()
        )


        if article is None:

            return JSONResponse(
                {
                    "success": False,
                    "error": "文章不存在",
                },
                status_code=404,
            )


        # 草稿/未发布文章禁止互动
        if article.status != "published":

            return JSONResponse(
                {
                    "success": False,
                    "error": "文章尚未发布，无法点赞",
                },
                status_code=400,
            )


        # ====================================================
        # 获取当前身份
        # ====================================================

        actor_name, visitor_id = get_actor_identity(
            request,
            nickname,
        )


        if not actor_name:

            return JSONResponse(
                {
                    "success": False,
                    "nickname_required": True,
                },
                status_code=401,
            )


        # ====================================================
        # 访客档案建档
        # ====================================================

        ensure_visitor(db, visitor_id, actor_name)

        db.flush()


        # ====================================================
        # 文章点赞：不查重，每次点击新增一条
        # ====================================================

        like = ArticleLike(
            article_id=article_id,
            visitor_id=visitor_id,
            nickname=actor_name,
        )

        db.add(like)

        db.commit()


        like_count = (
            db.query(ArticleLike)
            .filter(
                ArticleLike.article_id == article_id
            )
            .count()
        )


        return JSONResponse(
            {
                "success": True,
                "liked": True,
                "like_count": like_count,
                "nickname": actor_name,
            }
        )


    finally:

        db.close()


# ============================================================
# PUBLIC：文章评论
# 需求：平级评论 + reply_to_id（回复引用）
# ============================================================

@app.post("/article/{article_id}/comment")
def comment_article(
    request: Request,
    article_id: int,
    content: str = Form(...),
    nickname: str | None = Form(None),
    reply_to_id: int | None = Form(None),
):
    db = SessionLocal()

    try:

        article = (
            db.query(Article)
            .filter(
                Article.id == article_id
            )
            .first()
        )


        if article is None:

            return JSONResponse(
                {
                    "success": False,
                    "error": "文章不存在",
                },
                status_code=404,
            )


        # 草稿/未发布文章禁止互动
        if article.status != "published":

            return JSONResponse(
                {
                    "success": False,
                    "error": "文章尚未发布，无法评论",
                },
                status_code=400,
            )


        content = content.strip()


        if not content:

            return JSONResponse(
                {
                    "success": False,
                    "error": "评论内容不能为空",
                },
                status_code=400,
            )


        if len(content) > 1000:

            return JSONResponse(
                {
                    "success": False,
                    "error": "评论不能超过 1000 个字符",
                },
                status_code=400,
            )


        actor_name, visitor_id = get_actor_identity(
            request,
            nickname,
        )


        if not actor_name:

            return JSONResponse(
                {
                    "success": False,
                    "nickname_required": True,
                },
                status_code=401,
            )


        # ====================================================
        # 校验回复引用（可选）
        # ====================================================

        if reply_to_id is not None:

            reply_target = (
                db.query(ArticleComment)
                .filter(
                    ArticleComment.id == reply_to_id,
                    ArticleComment.article_id == article_id,
                )
                .first()
            )

            if reply_target is None:

                return JSONResponse(
                    {
                        "success": False,
                        "error": "回复的评论不存在",
                    },
                    status_code=400,
                )


        # ====================================================
        # 访客档案建档
        # ====================================================

        ensure_visitor(db, visitor_id, actor_name)

        db.flush()


        comment = ArticleComment(
            article_id=article.id,
            visitor_id=visitor_id,
            nickname=actor_name,
            content=content,
            reply_to_id=reply_to_id,
        )

        db.add(comment)

        db.commit()

        db.refresh(comment)


        comment_count = (
            db.query(ArticleComment)
            .filter(
                ArticleComment.article_id == article_id
            )
            .count()
        )


        reply_to_nickname = None

        if (
            reply_to_id is not None
            and reply_target is not None
        ):

            reply_to_nickname = reply_target.nickname


        return JSONResponse(
            {
                "success": True,
                "comment_id": comment.id,
                "nickname": actor_name,
                "content": comment.content,
                "comment_count": comment_count,
                "reply_to_id": reply_to_id,
                "reply_to_nickname": reply_to_nickname,
                "created_at": comment.created_at.strftime("%Y-%m-%d %H:%M"),
            }
        )


    finally:

        db.close()


# ============================================================
# PUBLIC：文章列表
# ============================================================

@app.get("/articles")
def articles_page(
    request: Request,
):

    db = SessionLocal()

    try:

        query = (
            db.query(Article)
            .options(
                selectinload(Article.likes),
                selectinload(Article.comments).selectinload(ArticleComment.reply_to),
            )
            .order_by(
                Article.created_at.desc()
            )
        )

        if not is_admin(request):

            query = query.filter(
                Article.status == "published"
            )

        articles = query.all()

        context = get_common_context(request)

        context["articles"] = articles

        return templates.TemplateResponse(
            request=request,
            name="articles.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# PUBLIC：朋友圈列表
# ============================================================

@app.get("/moments")
def moments_page(
    request: Request,
):

    db = SessionLocal()

    try:

        moments = (
            db.query(Moment)
            .options(
                selectinload(Moment.images),
                selectinload(Moment.likes),
                selectinload(Moment.comments).selectinload(MomentComment.reply_to),
            )
            .order_by(
                Moment.created_at.desc()
            )
            .all()
        )

        context = get_common_context(request)

        context["moments"] = moments

        context["liked_moment_ids"] = get_liked_moment_ids(
            db,
            get_visitor_id(request),
        )

        return templates.TemplateResponse(
            request=request,
            name="moments.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# PUBLIC：朋友圈详情页
# ============================================================

@app.get("/moment/{moment_id}")
def moment_detail(
    request: Request,
    moment_id: int,
):

    db = SessionLocal()

    try:

        moment = (
            db.query(Moment)
            .options(
                selectinload(Moment.images),
                selectinload(Moment.likes),
                selectinload(Moment.comments).selectinload(MomentComment.reply_to),
            )
            .filter(
                Moment.id == moment_id
            )
            .first()
        )


        if moment is None:

            raise HTTPException(
                status_code=404,
                detail="朋友圈不存在",
            )


        context = get_common_context(request)

        context["moment"] = moment

        context["liked_moment_ids"] = get_liked_moment_ids(
            db,
            get_visitor_id(request),
        )


        return templates.TemplateResponse(
            request=request,
            name="moment_detail.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# PUBLIC：留言列表
# 需求：MessageThread 多轮会话，公开/私密
# ============================================================

@app.get("/messages")
def messages_page(
    request: Request,
):

    db = SessionLocal()

    try:

        visitor_id = get_visitor_id(request)

        threads = (
            db.query(MessageThread)
            .options(
                selectinload(MessageThread.messages),
            )
            .order_by(
                MessageThread.updated_at.desc()
            )
            .all()
        )

        # 过滤：私密会话仅管理员或发布者本人可见
        visible_threads = []

        for thread in threads:

            if thread.is_private and not is_admin(request):

                if thread.visitor_id != visitor_id:

                    continue

            visible_threads.append(thread)


        context = get_common_context(request)

        context["threads"] = visible_threads

        return templates.TemplateResponse(
            request=request,
            name="messages.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# PUBLIC：留言详情页（会话）
# ============================================================

@app.get("/message/{thread_id}")
def message_detail(
    request: Request,
    thread_id: int,
):

    db = SessionLocal()

    try:

        thread = (
            db.query(MessageThread)
            .options(
                selectinload(MessageThread.messages),
            )
            .filter(
                MessageThread.id == thread_id
            )
            .first()
        )


        if thread is None:

            raise HTTPException(
                status_code=404,
                detail="留言不存在",
            )


        # 私密留言仅管理员或发布者本人可见
        if (
            thread.is_private
            and not is_admin(request)
        ):

            visitor_id = get_visitor_id(
                request
            )

            is_owner = (
                thread.visitor_id
                and thread.visitor_id == visitor_id
            )

            if not is_owner:

                raise HTTPException(
                    status_code=404,
                    detail="留言不存在",
                )


        context = get_common_context(request)

        context["thread"] = thread

        return templates.TemplateResponse(
            request=request,
            name="message_detail.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# PUBLIC：发布留言（新建会话）
# ============================================================

@app.post("/messages")
def create_message(
    request: Request,
    content: str = Form(...),
    nickname: str | None = Form(None),
    is_private: str | None = Form(None),
):
    db = SessionLocal()

    try:

        content = content.strip()


        if not content:

            return JSONResponse(
                {
                    "success": False,
                    "error": "留言内容不能为空",
                },
                status_code=400,
            )


        if len(content) > 2000:

            return JSONResponse(
                {
                    "success": False,
                    "error": "留言不能超过 2000 个字符",
                },
                status_code=400,
            )


        actor_name, visitor_id = get_actor_identity(
            request,
            nickname,
        )


        if not actor_name:

            return JSONResponse(
                {
                    "success": False,
                    "nickname_required": True,
                },
                status_code=401,
            )


        # 访客档案建档
        ensure_visitor(db, visitor_id, actor_name)

        db.flush()


        # 管理员创建时标记为管理员发送
        sender_type = (
            "admin"
            if is_admin(request)
            else "visitor"
        )

        # 创建会话（Thread）
        thread = MessageThread(
            visitor_id=visitor_id,
            is_private=bool(is_private == "true"),
        )

        db.add(thread)

        db.flush()


        # 首条留言
        message = Message(
            thread_id=thread.id,
            sender_type=sender_type,
            nickname=actor_name,
            content=content,
        )

        db.add(message)

        db.commit()

        db.refresh(message)


        response = JSONResponse(
            {
                "success": True,
                "nickname": actor_name,
                "content": message.content,
                "thread_id": thread.id,
            }
        )

        set_visitor_id_cookie(response, visitor_id)

        return response


    finally:

        db.close()


# ============================================================
# PUBLIC：回复留言（追加到会话）
# 权限：只有发布者本人或管理员可以回复
# ============================================================

@app.post("/message/{thread_id}/reply")
def reply_message(
    request: Request,
    thread_id: int,
    content: str = Form(...),
    nickname: str | None = Form(None),
):
    db = SessionLocal()

    try:

        thread = (
            db.query(MessageThread)
            .filter(
                MessageThread.id == thread_id
            )
            .first()
        )


        if thread is None:

            return JSONResponse(
                {
                    "success": False,
                    "error": "留言不存在",
                },
                status_code=404,
            )


        content = content.strip()


        if not content:

            return JSONResponse(
                {
                    "success": False,
                    "error": "回复内容不能为空",
                },
                status_code=400,
            )


        if len(content) > 1000:

            return JSONResponse(
                {
                    "success": False,
                    "error": "回复不能超过 1000 个字符",
                },
                status_code=400,
            )


        actor_name, visitor_id = get_actor_identity(
            request,
            nickname,
        )


        if not actor_name:

            return JSONResponse(
                {
                    "success": False,
                    "nickname_required": True,
                },
                status_code=401,
            )


        # ====================================================
        # 权限：只有发布者本人或管理员可以回复
        # ====================================================

        is_owner = (
            thread.visitor_id
            and thread.visitor_id == visitor_id
        )

        if not (is_admin(request) or is_owner):

            return JSONResponse(
                {
                    "success": False,
                    "error": "只有发布者或管理员可以回复",
                },
                status_code=403,
            )


        # 访客档案建档
        ensure_visitor(db, visitor_id, actor_name)

        db.flush()


        sender_type = (
            "admin"
            if is_admin(request)
            else "visitor"
        )

        reply = Message(
            thread_id=thread.id,
            sender_type=sender_type,
            nickname=actor_name,
            content=content,
        )

        db.add(reply)

        db.commit()

        db.refresh(reply)


        response = JSONResponse(
            {
                "success": True,
                "nickname": actor_name,
                "content": reply.content,
                "reply_id": reply.id,
            }
        )

        set_visitor_id_cookie(response, visitor_id)

        return response


    finally:

        db.close()


# ============================================================
# AUTHENTICATED：删除朋友圈
# ============================================================

@app.post("/admin/moment/{moment_id}/delete")
def delete_moment(
    request: Request,
    moment_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        moment = (
            db.query(Moment)
            .options(
                selectinload(Moment.images),
            )
            .filter(
                Moment.id == moment_id
            )
            .first()
        )


        if moment is None:

            return RedirectResponse(
                url="/moments",
                status_code=303,
            )


        # 收集图片磁盘路径，删除记录后一并清理文件，避免孤儿文件
        # 路径安全：仅允许清理 static/uploads/moments 目录下的物理文件，
        # 通过 realpath 解析后二次校验，防止路径穿越（../）越权删除
        base_dir = os.path.dirname(
            os.path.abspath(__file__)
        )

        moments_dir = os.path.realpath(
            os.path.join(
                base_dir,
                "static",
                "uploads",
                "moments",
            )
        )

        image_files = []

        for image in moment.images:

            if not image.image_path:
                continue

            # 仅接受 /static/uploads/moments/ 前缀的图片，且不允许 .. 穿越
            if (
                not image.image_path.startswith(
                    "/static/uploads/moments/"
                )
                or ".." in image.image_path
            ):
                continue

            rel_path = image.image_path[len("/static/"):]

            file_path = os.path.realpath(
                os.path.join(base_dir, rel_path)
            )

            # 解析后必须仍位于 moments 目录内（含其子目录）
            if (
                file_path == moments_dir
                or not file_path.startswith(
                    moments_dir + os.sep
                )
            ):
                continue

            image_files.append(file_path)


        db.delete(moment)

        db.commit()


        for file_path in image_files:

            try:

                # 文件不存在时不报错（FileNotFoundError 属于 OSError）
                if os.path.isfile(file_path):

                    os.remove(file_path)

            except OSError:

                pass


        return RedirectResponse(
            url="/moments",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：删除朋友圈评论
# ============================================================

@app.post("/admin/moment/comment/{comment_id}/delete")
def delete_moment_comment(
    request: Request,
    comment_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        comment = (
            db.query(MomentComment)
            .filter(
                MomentComment.id == comment_id
            )
            .first()
        )


        if comment is None:

            return RedirectResponse(
                url="/moments",
                status_code=303,
            )


        moment_id = comment.moment_id

        db.delete(comment)

        db.commit()


        return RedirectResponse(
            url=f"/moment/{moment_id}",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：删除文章评论
# ============================================================

@app.post("/admin/article/comment/{comment_id}/delete")
def delete_article_comment(
    request: Request,
    comment_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        comment = (
            db.query(ArticleComment)
            .filter(
                ArticleComment.id == comment_id
            )
            .first()
        )


        if comment is None:

            return RedirectResponse(
                url="/articles",
                status_code=303,
            )


        article_id = comment.article_id

        db.delete(comment)

        db.commit()


        return RedirectResponse(
            url=f"/article/{article_id}",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：删除留言会话
# ============================================================

@app.post("/admin/message/{thread_id}/delete")
def delete_message_thread(
    request: Request,
    thread_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        thread = (
            db.query(MessageThread)
            .filter(
                MessageThread.id == thread_id
            )
            .first()
        )


        if thread is None:

            return RedirectResponse(
                url="/messages",
                status_code=303,
            )


        db.delete(thread)

        db.commit()


        return RedirectResponse(
            url="/messages",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：删除留言会话中的单条消息
# ============================================================

@app.post("/admin/message/message/{message_id}/delete")
def delete_message_item(
    request: Request,
    message_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        message = (
            db.query(Message)
            .filter(
                Message.id == message_id
            )
            .first()
        )


        if message is None:

            return RedirectResponse(
                url="/messages",
                status_code=303,
            )


        thread_id = message.thread_id

        db.delete(message)

        db.commit()


        return RedirectResponse(
            url=f"/message/{thread_id}",
            status_code=303,
        )

    finally:

        db.close()
