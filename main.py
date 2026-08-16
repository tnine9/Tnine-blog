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
    Moment,
    MomentImage,
    MomentLike,
    MomentComment,
    Message,
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
# 权限
# ============================================================

def get_current_admin(request: Request):
    return request.session.get("admin_id")


def require_admin(request: Request):
    return get_current_admin(request)


def require_guest(request: Request):
    return get_current_admin(request) is None


def is_admin(request: Request):
    return get_current_admin(request) is not None


def get_common_context(request: Request):
    return {
        "is_admin": is_admin(request),
        "admin_username": request.session.get(
            "admin_username"
        ),
    }


# ============================================================
# 访客昵称
# ============================================================

VISITOR_NICKNAME_COOKIE = "tnine_nickname"

VISITOR_ID_COOKIE = "tnine_visitor_id"

ANONYMOUS_GUEST_NAME = "匿名访客"


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
    把访客 ID 写入响应 Cookie（180 天）。
    """

    response.set_cookie(
        key=VISITOR_ID_COOKIE,
        value=visitor_id,
        max_age=60 * 60 * 24 * 180,
        httponly=True,
        samesite="lax",
        path="/",
    )


def get_actor_name(
    request: Request,
    fallback_nickname: str | None = None,
):
    """
    获取当前互动用户名称。

    管理员：
        使用管理员账号

    游客：
        优先使用本次操作传入的昵称
        没有则使用 Cookie
        都没有则返回 None
    """

    # 管理员
    if is_admin(request):

        return request.session.get(
            "admin_username"
        )


    # 本次操作明确指定昵称
    if fallback_nickname is not None:

        nickname = fallback_nickname.strip()

        if nickname:

            return nickname[:50]

        return None


    # Cookie
    nickname = get_visitor_nickname(request)

    if nickname:

        return nickname.strip()[:50]


    return None


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
                selectinload(Article.comments),
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
               selectinload(Moment.comments),
            )
            .order_by(
               Moment.created_at.desc()
            ) 
            .all()
        )


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


        # 按时间倒序

        timeline.sort(
            key=lambda x: x["data"].created_at,
            reverse=True
        )


        context = get_common_context(request)

        context["timeline"] = timeline

        context["liked_moment_ids"] = request.session.get(
            "liked_moment_ids",
            []
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
                selectinload(Article.comments),
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
                    "extra",
                    "sane_lists",
                    "toc",
                ],
            ),
            attributes={
                "a": {"href", "title", "class"},
                "img": {"src", "alt", "title"},
                "h1": {"id"},
                "h2": {"id"},
                "h3": {"id"},
                "h4": {"id"},
                "code": {"class"},
                "pre": {"class"},
            },
        )


        # ====================================================
        # 当前用户是否已点赞
        # ====================================================

        actor_name = get_actor_name(request)

        liked_article = False

        if actor_name:

            liked_article = (
                db.query(ArticleLike)
                .filter(
                    ArticleLike.article_id == article.id,
                    ArticleLike.nickname == actor_name,
                )
                .first()
                is not None
            )


        context = get_common_context(request)

        context["article"] = article
        context["article_html"] = article_html
        context["liked_article"] = liked_article

        return templates.TemplateResponse(
            request=request,
            name="article_detail.html",
            context=context,
        )

    finally:
        db.close()


# ============================================================
# GUEST：管理员登录页面
# ============================================================

@app.get("/admin/login")
def admin_login_page(
    request: Request,
):

    # 已经登录
    if not require_guest(request):

        return RedirectResponse(
            url="/admin",
            status_code=303,
        )


    db = SessionLocal()

    try:

        # ====================================================
        # 检查系统是否已经存在管理员
        # ====================================================

        admin_count = (
            db.query(Admin)
            .count()
        )


        # 没有任何管理员
        # 自动进入首次创建管理员页面

        if admin_count == 0:

            return RedirectResponse(
                url="/admin/register",
                status_code=303,
            )


        context = get_common_context(request)

        context["error"] = None


        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context=context,
        )

    finally:

        db.close()

# ============================================================
# PUBLIC：文章页面
# ============================================================

@app.get("/articles")
def articles(request: Request):

    db = SessionLocal()

    try:

        articles = (
            db.query(Article)
            .filter(
                Article.status == "published"
            )
            .options(
                selectinload(Article.likes),
                selectinload(Article.comments),
            )
            .order_by(
                Article.created_at.desc()
            )
            .all()
        )


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
# PUBLIC：朋友圈页面
# ============================================================

@app.get("/moments")
def moments(request: Request):

    db = SessionLocal()

    try:

        moments = (
            db.query(Moment)
            .options(
                selectinload(Moment.images),
                selectinload(Moment.likes),
                selectinload(Moment.comments),
            )
            .order_by(
                Moment.created_at.desc()
            )
            .all()
        )


        context = get_common_context(request)


        context["moments"] = moments


        context["liked_moment_ids"] = request.session.get(
            "liked_moment_ids",
            []
        )


        return templates.TemplateResponse(
            request=request,
            name="moments.html",
            context=context,
        )


    finally:

        db.close()



# ============================================================
# PUBLIC：留言页面
# ============================================================

@app.get("/messages")
def messages(
    request: Request,
):

    db = SessionLocal()

    try:

        # 非管理员只能看到非私密留言
        query = (
            db.query(Message)
            .filter(
                Message.parent_id.is_(None)
            )
        )

        if not is_admin(request):

            visitor_id = get_visitor_id(
                request
            )

            query = query.filter(
                or_(
                    Message.is_private.is_(False),
                    Message.visitor_id == visitor_id,
                )
            )

        messages = (
            query
            .order_by(
                Message.created_at.desc()
            )
            .all()
        )


        # 预加载回复（详情页展示使用）
        for message in messages:

            message.replies


        context = get_common_context(request)


        context["messages"] = messages

        # 当前访客 ID（用于判断"发布者本人"权限）
        context["visitor_id"] = get_visitor_id(
            request
        )


        return templates.TemplateResponse(
            request=request,
            name="messages.html",
            context=context,
        )


    finally:

        db.close()

# ============================================================
# GUEST：登录
# ============================================================

@app.post("/admin/login")
def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):

    if not require_guest(request):
        return RedirectResponse(
            url="/admin",
            status_code=303,
        )

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

            context["error"] = (
                "用户名或密码错误"
            )

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

            context["error"] = (
                "用户名或密码错误"
            )

            return templates.TemplateResponse(
                request=request,
                name="admin_login.html",
                context=context,
            )


        request.session["admin_id"] = admin.id

        request.session[
            "admin_username"
        ] = admin.username


        return RedirectResponse(
            url="/admin",
            status_code=303,
        )

    finally:
        db.close()


# ============================================================
# GUEST：首次创建管理员页面
# ============================================================

@app.get("/admin/register")
def admin_register_page(
    request: Request,
):

    # 已经登录
    if not require_guest(request):

        return RedirectResponse(
            url="/admin",
            status_code=303,
        )


    db = SessionLocal()

    try:

        # 如果已经存在管理员，
        # 就不能再通过这个页面创建

        admin_count = (
            db.query(Admin)
            .count()
        )


        if admin_count > 0:

            return RedirectResponse(
                url="/admin/login",
                status_code=303,
            )


        context = get_common_context(request)

        context["error"] = None


        return templates.TemplateResponse(
            request=request,
            name="admin_register.html",
            context=context,
        )

    finally:

        db.close()



# ============================================================
# GUEST：创建第一个管理员
# ============================================================

@app.post("/admin/register")
def admin_register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):

    if not require_guest(request):

        return RedirectResponse(
            url="/admin",
            status_code=303,
        )


    username = username.strip()


    db = SessionLocal()

    try:

        # ====================================================
        # 再次检查
        # 防止已经存在管理员时绕过前端访问
        # ====================================================

        admin_count = (
            db.query(Admin)
            .count()
        )


        if admin_count > 0:

            return RedirectResponse(
                url="/admin/login",
                status_code=303,
            )


        # ====================================================
        # 基础验证
        # ====================================================

        if not username:

            context = get_common_context(request)

            context["error"] = "用户名不能为空"

            return templates.TemplateResponse(
                request=request,
                name="admin_register.html",
                context=context,
            )


        if not password:

            context = get_common_context(request)

            context["error"] = "密码不能为空"

            return templates.TemplateResponse(
                request=request,
                name="admin_register.html",
                context=context,
            )


        if len(password) < 6:

            context = get_common_context(request)

            context["error"] = "密码至少需要 6 位"

            return templates.TemplateResponse(
                request=request,
                name="admin_register.html",
                context=context,
            )


        if password != confirm_password:

            context = get_common_context(request)

            context["error"] = "两次输入的密码不一致"

            return templates.TemplateResponse(
                request=request,
                name="admin_register.html",
                context=context,
            )


        # ====================================================
        # 创建管理员
        # ====================================================

        password_hash = (
            password_hasher.hash(password)
        )


        admin = Admin(
            username=username,
            password_hash=password_hash,
        )


        db.add(admin)

        db.commit()

        db.refresh(admin)


        # ====================================================
        # 创建成功后直接登录
        # ====================================================

        request.session["admin_id"] = admin.id

        request.session[
            "admin_username"
        ] = admin.username


        return RedirectResponse(
            url="/admin",
            status_code=303,
        )

    finally:

        db.close()
        
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


        return templates.TemplateResponse(
            request=request,
            name="admin_home.html",
            context=context,
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
                "admin_username",
                "管理员"
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
        保存 180 天 Cookie

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
            max_age=60 * 60 * 24 * 180,
            httponly=True,
            samesite="lax",
            path="/",
        )

    else:

        response.delete_cookie(
            key=VISITOR_NICKNAME_COOKIE,
            path="/",
        )


    return response


# ============================================================
# PUBLIC：朋友圈点赞 / 取消点赞
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

        actor_name = get_actor_name(
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
        # 查询当前昵称是否已经点赞
        # ====================================================

        existing_like = (
            db.query(MomentLike)
            .filter(
                MomentLike.moment_id == moment_id,
                MomentLike.nickname == actor_name,
            )
            .first()
        )


        # ====================================================
        # 已点赞 → 保持点赞（不支持取消）
        # ====================================================

        if existing_like:

            db.commit()


            # 记录会话已赞状态（刷新后仍显示"已赞"）

            liked_ids = request.session.get(
                "liked_moment_ids",
                []
            )

            if moment_id not in liked_ids:

                liked_ids.append(moment_id)

                request.session["liked_moment_ids"] = liked_ids

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
            nickname=actor_name,
        )

        db.add(like)

        liked = True


        db.commit()


        # 记录会话已赞状态（刷新后仍显示"已赞"）

        liked_ids = request.session.get(
            "liked_moment_ids",
            []
        )

        if moment_id not in liked_ids:

            liked_ids.append(moment_id)

            request.session["liked_moment_ids"] = liked_ids


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
# ============================================================

@app.post("/moment/{moment_id}/comment")
def comment_moment(
    request: Request,
    moment_id: int,
    content: str = Form(...),
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

        actor_name = get_actor_name(
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
        # 保存评论
        # ====================================================

        comment = MomentComment(
            moment_id=moment.id,
            nickname=actor_name,
            content=content,
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


        return JSONResponse(
            {
                "success": True,
                "nickname": actor_name,
                "content": comment.content,
                "comment_count": comment_count,
            }
        )


    finally:

        db.close()


# ============================================================
# PUBLIC：文章点赞
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


        # ====================================================
        # 获取当前身份
        # ====================================================

        actor_name = get_actor_name(
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
        # 已点赞 → 保持点赞（不支持取消）
        # ====================================================

        existing_like = (
            db.query(ArticleLike)
            .filter(
                ArticleLike.article_id == article_id,
                ArticleLike.nickname == actor_name,
            )
            .first()
        )


        if existing_like:

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
                    "already_liked": True,
                    "like_count": like_count,
                    "nickname": actor_name,
                }
            )


        # ====================================================
        # 未点赞 → 新增
        # ====================================================

        like = ArticleLike(
            article_id=article_id,
            nickname=actor_name,
        )

        db.add(like)

        liked = True

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
                "liked": liked,
                "like_count": like_count,
                "nickname": actor_name,
            }
        )


    finally:

        db.close()


# ============================================================
# PUBLIC：文章评论
# ============================================================

@app.post("/article/{article_id}/comment")
def comment_article(
    request: Request,
    article_id: int,
    content: str = Form(...),
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


        actor_name = get_actor_name(
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


        comment = ArticleComment(
            article_id=article.id,
            nickname=actor_name,
            content=content,
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


        return JSONResponse(
            {
                "success": True,
                "nickname": actor_name,
                "content": comment.content,
                "comment_count": comment_count,
            }
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
                selectinload(Moment.comments),
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

        context["liked_moment_ids"] = request.session.get(
            "liked_moment_ids",
            []
        )


        return templates.TemplateResponse(
            request=request,
            name="moment_detail.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# PUBLIC：留言详情页
# ============================================================

@app.get("/message/{message_id}")
def message_detail(
    request: Request,
    message_id: int,
):

    db = SessionLocal()

    try:

        message = (
            db.query(Message)
            .options(
                selectinload(Message.replies),
            )
            .filter(
                Message.id == message_id
            )
            .first()
        )


        if message is None:

            raise HTTPException(
                status_code=404,
                detail="留言不存在",
            )


        # 私密留言仅管理员或发布者本人可见
        if (
            message.is_private
            and not is_admin(request)
        ):

            visitor_id = get_visitor_id(
                request
            )

            is_owner = (
                message.visitor_id
                and message.visitor_id == visitor_id
            )

            if not is_owner:

                raise HTTPException(
                    status_code=404,
                    detail="留言不存在",
                )


        context = get_common_context(request)

        context["message"] = message

        context["visitor_id"] = get_visitor_id(
            request
        )


        return templates.TemplateResponse(
            request=request,
            name="message_detail.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# PUBLIC：发布留言
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


        actor_name = get_actor_name(
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


        # 访客唯一标识（发布者本人识别）
        visitor_id = get_visitor_id(request)

        message = Message(
            nickname=actor_name,
            content=content,
            is_private=bool(is_private == "true"),
            visitor_id=visitor_id,
        )

        db.add(message)

        db.commit()

        db.refresh(message)


        response = JSONResponse(
            {
                "success": True,
                "nickname": actor_name,
                "content": message.content,
                "message_id": message.id,
            }
        )

        set_visitor_id_cookie(response, visitor_id)

        return response


    finally:

        db.close()


# ============================================================
# PUBLIC：回复留言
# ============================================================

@app.post("/message/{message_id}/reply")
def reply_message(
    request: Request,
    message_id: int,
    content: str = Form(...),
    nickname: str | None = Form(None),
):
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

            return JSONResponse(
                {
                    "success": False,
                    "error": "留言不存在",
                },
                status_code=404,
            )


        # 只有顶层留言可以回复
        if message.parent_id is not None:

            return JSONResponse(
                {
                    "success": False,
                    "error": "只能回复顶层留言",
                },
                status_code=400,
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


        actor_name = get_actor_name(
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

        visitor_id = get_visitor_id(request)

        is_owner = (
            message.visitor_id
            and message.visitor_id == visitor_id
        )

        if not (is_admin(request) or is_owner):

            return JSONResponse(
                {
                    "success": False,
                    "error": "只有发布者或管理员可以回复",
                },
                status_code=403,
            )


        reply = Message(
            nickname=actor_name,
            content=content,
            is_private=False,
            visitor_id=visitor_id,
            parent_id=message.id,
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
        image_files = []

        for image in moment.images:

            if (
                image.image_path
                and image.image_path.startswith("/static/uploads/")
            ):

                image_files.append(
                    image.image_path[len("/static/"):]
                )


        db.delete(moment)

        db.commit()


        for rel_path in image_files:

            try:

                file_path = os.path.join(
                    os.path.dirname(
                        os.path.abspath(__file__)
                    ),
                    rel_path,
                )


                if (
                    os.path.isfile(file_path)
                    and os.path.dirname(file_path).endswith(
                        os.path.join("static", "uploads")
                    )
                ):

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
# AUTHENTICATED：删除留言
# ============================================================

@app.post("/admin/message/{message_id}/delete")
def delete_message(
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


        db.delete(message)

        db.commit()


        return RedirectResponse(
            url="/messages",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：删除留言回复
# ============================================================

@app.post("/admin/message/reply/{reply_id}/delete")
def delete_message_reply(
    request: Request,
    reply_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        reply = (
            db.query(Message)
            .filter(
                Message.id == reply_id
            )
            .first()
        )


        if reply is None:

            return RedirectResponse(
                url="/messages",
                status_code=303,
            )


        parent_id = reply.parent_id

        db.delete(reply)

        db.commit()


        return RedirectResponse(
            url=f"/message/{parent_id}",
            status_code=303,
        )

    finally:

        db.close()