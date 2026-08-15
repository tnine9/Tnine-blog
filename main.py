from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pwdlib import PasswordHash
import markdown
from sqlalchemy.orm import selectinload

from database import SessionLocal, Base, engine
from models import (
    Article,
    Admin,
    Moment,
    MomentImage,
    MomentLike,
    MomentComment,
)

from fastapi import UploadFile, File
import os
import shutil


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
    secret_key="Tnine-dev-secret-2026",
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
            .filter(
                Article.id == article_id
            )
            .first()
        )

        if article is None:
            return {"error": "文章不存在"}


        # ====================================================
        # 草稿保护
        # ====================================================

        # 非管理员不能查看草稿
        if (
            article.status != "published"
            and not is_admin(request)
        ):
            return {"error": "文章不存在"}


        # Markdown → HTML
        article_html = markdown.markdown(
            article.content,
            extensions=[
                "extra",
                "sane_lists",
                "toc",
            ],
        )


        context = get_common_context(request)

        context["article"] = article
        context["article_html"] = article_html

        return templates.TemplateResponse(
            request=request,
            name="article.html",
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
            title=title,
            summary=summary,
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
            return {
                "error": "文章不存在"
            }

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

            return {"error": "文章不存在"}


        # 更新正文
        article.title = title
        article.summary = summary
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

            return {"error": "文章不存在"}


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
    images: list[UploadFile] = File(default=[]),
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

        for index, image in enumerate(images):

            if image.filename:


                filename = (
                    f"{moment.id}_"
                    f"{index}_"
                    f"{image.filename}"
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

print("========== 当前路由 ==========")

for route in app.routes:
    print(route.path)

# ============================================================
# PUBLIC：朋友圈点赞
# ============================================================

@app.post("/moment/{moment_id}/like")
def like_moment(
    request: Request,
    moment_id: int,
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
            return RedirectResponse(
                url="/",
                status_code=303,
            )

        liked_moments = request.session.get(
            "liked_moment_ids",
            []
        )

        # 已经点过就不重复增加
        if moment_id not in liked_moments:

            nickname = request.session.get(
                "admin_username",
                "匿名用户"
            )

            like = MomentLike(
                moment_id=moment.id,
                nickname=nickname,
            )

            db.add(like)

            db.commit()

            liked_moments.append(moment_id)

            # 防止 session 无限变大
            request.session["liked_moment_ids"] = (
                liked_moments[-100:]
            )

        return RedirectResponse(
            url="/",
            status_code=303,
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
    nickname: str = Form("匿名用户"),
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
            return RedirectResponse(
                url="/",
                status_code=303,
            )

        content = content.strip()

        if not content:
            return RedirectResponse(
                url="/",
                status_code=303,
            )

        # 登录用户直接使用登录名
        if is_admin(request):
            nickname = request.session.get(
                "admin_username",
                "管理员"
            )
        else:
            nickname = nickname.strip()[:50]

            if not nickname:
                nickname = "匿名用户"

        comment = MomentComment(
            moment_id=moment.id,
            nickname=nickname,
            content=content[:1000],
        )

        db.add(comment)

        db.commit()

        return RedirectResponse(
            url="/",
            status_code=303,
        )

    finally:
        db.close()