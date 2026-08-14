from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pwdlib import PasswordHash
import markdown

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
# GUEST：登录页面
# ============================================================

@app.get("/admin/login")
def admin_login_page(
    request: Request,
):

    if not require_guest(request):
        return RedirectResponse(
            url="/admin",
            status_code=303,
        )

    context = get_common_context(request)

    context["error"] = None

    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context=context,
    )


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