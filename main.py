from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pwdlib import PasswordHash
import markdown
import nh3
from sqlalchemy import or_, func
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
    Tag,
    ArticleTag,
    SocialLink,
    HeroBackground,
    Notification,
)

import notifications_service

from fastapi import UploadFile, File
import os
import shutil
import uuid
import secrets
import random
import smtplib
import hashlib
import hmac
import base64
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import formataddr
from urllib.parse import quote


# ============================================================
# 数据库初始化
# ============================================================

Base.metadata.create_all(bind=engine)


# ============================================================
# FastAPI
# ============================================================

app = FastAPI()


# 生产环境（HTTPS）下开启 Secure Cookie
SECURE_COOKIES = (
    os.environ.get("TNINE_ENV") == "production"
)


# ============================================================
# Session
# 安全要求：
# - HttpOnly：Starlette SessionMiddleware 默认开启
# - SameSite=lax：Starlette 默认
# - 生产环境（TNINE_ENV=production，HTTPS）开启 Secure Cookie
# ============================================================

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get(
        "TNINE_SECRET_KEY",
        "Tnine-dev-secret-2026",
    ),
    https_only=SECURE_COOKIES,
)


# ============================================================
# 密码
# ============================================================

password_hasher = PasswordHash.recommended()


# ============================================================
# 管理员初始化状态
# 需求：
# - 账号固定 admin，不可注册
# - admin 不存在时进入初始化状态：生成初始密码 + 一次性初始化验证码
# - 初始密码高强度随机，不硬编码、不落库（仅存内存）
# - 首次初始化登录成功后创建 admin 记录，初始密码即正式密码
# 说明：
# - 初始化状态保存在进程内存，不写入数据库
# - 仅适用于「admins 表为空」的首次启动；已有管理员时不会触发
# - 多 worker/多进程部署下请保证初始化在单进程完成（本地开发单进程即可）
# ============================================================

INIT_PASSWORD_LENGTH = 10

INIT_CODE_LENGTH = 6

INIT_CODE_CHARS = "0123456789"

INIT_PASSWORD_CHARS = (
    "ABCDEFGHJKLMNPQRSTUVWXYZ"
    "abcdefghjkmnpqrstuvwxyz"
    "23456789"
)


def generate_random_password(length=INIT_PASSWORD_LENGTH):
    """
    生成高强度随机密码（示例格式：X8kP29mQ7a）。
    """

    return "".join(
        secrets.choice(INIT_PASSWORD_CHARS)
        for _ in range(length)
    )


def generate_init_code(length=INIT_CODE_LENGTH):
    """
    生成一次性初始化验证码（纯数字，示例格式：739214）。
    """

    return "".join(
        secrets.choice(INIT_CODE_CHARS)
        for _ in range(length)
    )


_admin_init_state = None


def get_admin_init_state():
    """
    获取（必要时生成）管理员初始化状态。

    返回 None 表示 admin 已存在、无需初始化；
    否则返回 dict：
    {
        "password": 初始密码明文（仅内存，用于页面自动填充与校验）,
        "password_hash": 初始密码哈希,
        "code": 初始化验证码明文,
        "code_hash": 初始化验证码哈希,
    }
    """

    global _admin_init_state

    db = SessionLocal()

    try:

        admin_count = db.query(Admin).count()

        if admin_count > 0:

            # 已存在管理员，清除残留初始化状态
            _admin_init_state = None

            return None

    finally:

        db.close()

    if _admin_init_state is None:

        password = generate_random_password()

        code = generate_init_code()

        _admin_init_state = {
            "password": password,
            "password_hash": password_hasher.hash(password),
            "code": code,
            "code_hash": password_hasher.hash(code),
        }

        print(
            "[Tnine] 系统尚未初始化管理员账号，"
            "已生成初始密码与一次性初始化验证码。"
        )

    return _admin_init_state


def clear_admin_init_state():
    """
    首次初始化登录成功后清除初始化状态，
    初始化验证码立即失效、不可再次使用。
    """

    global _admin_init_state

    _admin_init_state = None


def is_admin(request: Request):
    """
    判断当前请求是否为已登录的管理员（Session 登录态）。
    """

    return request.session.get("admin_id") is not None


def require_admin(request: Request):
    """
    后台路由守卫：未登录返回 None（调用方跳转 /admin/login）；
    已登录返回 admin 对象。
    """

    admin_id = request.session.get("admin_id")

    if not admin_id:

        return None

    db = SessionLocal()

    try:

        return (
            db.query(Admin)
            .filter(Admin.id == admin_id)
            .first()
        )

    finally:

        db.close()


# ============================================================
# 邮箱配置（后台可配置，存储于 Setting 表）
# 需求：
# - 支持发件邮箱（SMTP 登录）与管理员收件邮箱，可同可异
# - 未单独配置收件邮箱时默认 收件邮箱 = 发件邮箱
# - 邮箱密码禁止明文存储（使用轻量对称加密，密钥来自环境变量）
# - 提供环境变量默认值：TNINE_SMTP_HOST / TNINE_SMTP_PORT /
#   TNINE_SMTP_USERNAME / TNINE_MAIL_PASSWORD / TNINE_MAIL_FROM /
#   TNINE_MAIL_TO；后台配置优先于环境变量
# ============================================================

EMAIL_SMTP_HOST_KEY = "admin_email_smtp_host"

EMAIL_SMTP_PORT_KEY = "admin_email_smtp_port"

EMAIL_SMTP_USERNAME_KEY = "admin_email_smtp_username"

EMAIL_SMTP_PASSWORD_ENC_KEY = "admin_email_smtp_password_enc"

EMAIL_FROM_KEY = "admin_email_from"

EMAIL_TO_KEY = "admin_email_to"

EMAIL_USE_TLS_KEY = "admin_email_use_tls"

# 邮箱密码加密密钥：优先环境变量 TNINE_MAIL_SECRET_KEY，
# 未设置时使用内置开发密钥（本地开发可用，生产请显式配置）
MAIL_SECRET_KEY = os.environ.get(
    "TNINE_MAIL_SECRET_KEY",
    "Tnine-mail-secret-2026",
)


def _mail_derive_key(secret: str, salt: bytes):
    """
    从主密钥派生固定长度的加密密钥。
    """

    return hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt,
        iterations=100_000,
        dklen=32,
    )


def _xor_stream(key: bytes, nonce: bytes, length: int) -> bytes:
    """
    使用 PBKDF2 派生的密钥流（计数器模式）加密/解密。
    """

    out = bytearray()

    counter = 0

    while len(out) < length:

        block = hashlib.sha256(
            key + nonce + counter.to_bytes(4, "big")
        ).digest()

        out.extend(block)

        counter += 1

    return bytes(out[:length])


def encrypt_secret(plaintext: str) -> str:
    """
    轻量对称加密（PBKDF2 密钥流 + HMAC 完整性校验），
    防止邮箱密码等敏感配置以明文落库。
    返回格式：enc:v1:<salt_b64>:<nonce_b64>:<cipher_b64>:<mac_b64>
    生产环境建议替换为更强制密方案（如 KMS / 独立 secrets 服务）。
    """

    if not plaintext:
        return ""

    salt = secrets.token_bytes(16)

    nonce = secrets.token_bytes(8)

    key = _mail_derive_key(MAIL_SECRET_KEY, salt)

    stream = _xor_stream(key, nonce, len(plaintext.encode("utf-8")))

    cipher = bytes(
        a ^ b
        for a, b in zip(
            plaintext.encode("utf-8"),
            stream,
        )
    )

    mac = hmac.new(
        key,
        salt + nonce + cipher,
        hashlib.sha256,
    ).digest()

    return "enc:v1:" + ":".join(
        base64.b64encode(part).decode("ascii")
        for part in (salt, nonce, cipher, mac)
    )


def decrypt_secret(stored: str) -> str:
    """
    解密 encrypt_secret 的密文；无法解析或校验失败时返回空字符串。
    """

    if not stored or not stored.startswith("enc:v1:"):
        return ""

    try:

        parts = stored.split(":", 2)[2].split(":")

        salt = base64.b64decode(parts[0])

        nonce = base64.b64decode(parts[1])

        cipher = base64.b64decode(parts[2])

        mac = base64.b64decode(parts[3])

        key = _mail_derive_key(MAIL_SECRET_KEY, salt)

        expected = hmac.new(
            key,
            salt + nonce + cipher,
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(expected, mac):
            return ""

        stream = _xor_stream(key, nonce, len(cipher))

        plaintext = bytes(
            a ^ b
            for a, b in zip(
                cipher,
                stream,
            )
        )

        return plaintext.decode("utf-8")

    except Exception:

        return ""


def _get_setting_value(db, key: str, default: str = "") -> str:
    setting = (
        db.query(Setting)
        .filter(Setting.key == key)
        .first()
    )

    if setting is None:
        return default

    return setting.value or default


def _set_setting_value(db, key: str, value: str):
    setting = (
        db.query(Setting)
        .filter(Setting.key == key)
        .first()
    )

    if setting is None:
        setting = Setting(key=key, value=value)
        db.add(setting)
    else:
        setting.value = value


def get_mail_config(db):
    """
    读取当前邮箱配置（后台配置优先，其次环境变量）。

    返回 dict：
    - host / port / username / from_addr / to_addr / use_tls / password
    - configured：是否已有完整可用的发件配置
    """

    host = _get_setting_value(
        db, EMAIL_SMTP_HOST_KEY,
        os.environ.get("TNINE_SMTP_HOST", ""),
    )

    port_raw = _get_setting_value(
        db, EMAIL_SMTP_PORT_KEY,
        os.environ.get("TNINE_SMTP_PORT", "465"),
    )

    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        port = 465

    username = _get_setting_value(
        db, EMAIL_SMTP_USERNAME_KEY,
        os.environ.get("TNINE_SMTP_USERNAME", ""),
    )

    from_addr = _get_setting_value(
        db, EMAIL_FROM_KEY,
        os.environ.get("TNINE_MAIL_FROM", username),
    )

    to_addr = _get_setting_value(
        db, EMAIL_TO_KEY,
        os.environ.get("TNINE_MAIL_TO", ""),
    )

    # 未单独配置收件邮箱时默认 收件邮箱 = 发件邮箱
    if not to_addr:
        to_addr = from_addr

    use_tls = _get_setting_value(
        db, EMAIL_USE_TLS_KEY,
        os.environ.get("TNINE_SMTP_USE_TLS", "1"),
    ).lower() in ("1", "true", "yes", "on")

    stored_enc = _get_setting_value(
        db, EMAIL_SMTP_PASSWORD_ENC_KEY, "",
    )

    password = decrypt_secret(stored_enc)

    if not password:
        password = os.environ.get("TNINE_MAIL_PASSWORD", "")

    configured = bool(
        host and port and username and from_addr and password
    )

    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "from_addr": from_addr,
        "to_addr": to_addr,
        "use_tls": use_tls,
        "configured": configured,
    }


def send_login_code_mail(
    db,
    code: str,
):
    """
    发送登录验证码邮件到管理员收件邮箱。

    返回：
    - ok: True 发送成功
    - ok: False, reason: 失败原因（配置缺失 / SMTP 异常等）
    - dev_code: 开发模式（非 production）下配置缺失时返回验证码，
      便于本地联调；生产模式绝不返回验证码
    """

    config = get_mail_config(db)

    dev_code = None

    if not config["configured"]:

        reason = (
            "邮箱未配置（SMTP 主机/端口/发件邮箱/邮箱密码不完整），"
            "请在后台「邮箱配置」中填写，或设置环境变量 "
            "TNINE_SMTP_HOST / TNINE_SMTP_PORT / "
            "TNINE_SMTP_USERNAME / TNINE_MAIL_PASSWORD / "
            "TNINE_MAIL_FROM / TNINE_MAIL_TO。"
        )

        if not (os.environ.get("TNINE_ENV") == "production"):

            dev_code = code

            print(
                "[Tnine][开发模式] 登录验证码未通过 SMTP 发送："
                + reason
            )

            print(
                "[Tnine][开发模式] 登录验证码："
                + code
                + "（收件邮箱："
                + (config["to_addr"] or "未配置")
                + "）"
            )

        return {
            "ok": False,
            "reason": reason,
            "dev_code": dev_code,
        }

    subject = "【Tnine】管理员登录验证码"

    body = (
        "你的 Tnine 管理员登录验证码是："
        + code
        + "\n\n验证码 5 分钟内有效，请勿泄露给他人。"
    )

    try:

        if config["use_tls"]:

            server = smtplib.SMTP(
                config["host"],
                config["port"],
                timeout=15,
            )

            server.starttls()

        else:

            server = smtplib.SMTP_SSL(
                config["host"],
                config["port"],
                timeout=15,
            )

        server.login(
            config["username"],
            config["password"],
        )

        message = MIMEText(body, "plain", "utf-8")

        message["Subject"] = Header(subject, "utf-8")

        message["From"] = formataddr(
            ("Tnine 管理员", config["from_addr"])
        )

        message["To"] = config["to_addr"]

        server.sendmail(
            config["from_addr"],
            [config["to_addr"]],
            message.as_string(),
        )

        server.quit()

        return {
            "ok": True,
            "reason": "",
            "dev_code": None,
        }

    except Exception as exc:

        reason = "SMTP 发送失败：" + str(exc)

        if not (os.environ.get("TNINE_ENV") == "production"):

            dev_code = code

            print("[Tnine][开发模式] " + reason)

            print("[Tnine][开发模式] 登录验证码：" + code)

        return {
            "ok": False,
            "reason": reason,
            "dev_code": dev_code,
        }


# ============================================================
# 邮箱登录验证码（内存态，5 分钟有效，一次性）
# ============================================================

LOGIN_CODE_TTL_SECONDS = 5 * 60

_login_codes = {}


def generate_login_code():
    """
    生成 6 位数字登录验证码，并记录其哈希与过期时间。
    重新发送时旧验证码立即失效。
    """

    global _login_codes

    code = "".join(
        secrets.choice(INIT_CODE_CHARS)
        for _ in range(6)
    )

    _login_codes = {
        "hash": hashlib.sha256(
            code.encode("utf-8")
        ).hexdigest(),
        "expires_at": (
            datetime.now().timestamp()
            + LOGIN_CODE_TTL_SECONDS
        ),
    }

    return code


def verify_login_code(code: str) -> bool:
    """
    校验登录验证码：命中且未过期则通过，并立即失效（一次性）。
    """

    global _login_codes

    stored = _login_codes

    if not stored:
        return False

    _login_codes = {}

    if (
        datetime.now().timestamp()
        > stored["expires_at"]
    ):
        return False

    candidate = hashlib.sha256(
        code.strip().encode("utf-8")
    ).hexdigest()

    return hmac.compare_digest(
        candidate,
        stored["hash"],
    )


def send_admin_login_code(db):
    """
    生成并发送管理员登录验证码。
    返回与 send_login_code_mail 相同的结构。
    """

    code = generate_login_code()

    return send_login_code_mail(db, code)


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


# ============================================================
# 通用配置读取/写入（Setting 表）
# ============================================================

def get_setting_value(key: str, default: str = ""):
    """
    读取 Setting 配置，不存在时返回默认值。
    """

    db = SessionLocal()

    try:

        setting = (
            db.query(Setting)
            .filter(Setting.key == key)
            .first()
        )

        if setting is None:

            return default

        return setting.value

    finally:

        db.close()


def set_setting_value(key: str, value: str):
    """
    写入 Setting 配置（不存在则创建）。
    """

    db = SessionLocal()

    try:

        setting = (
            db.query(Setting)
            .filter(Setting.key == key)
            .first()
        )

        if setting is None:

            setting = Setting(
                key=key,
                value=value,
            )

            db.add(setting)

        else:

            setting.value = value

        db.commit()

        return True

    finally:

        db.close()


# ============================================================
# Hero 首屏系统
# 配置存储于 Setting 表，背景资源存储于 hero_backgrounds 表
# ============================================================

HERO_BG_MODES = ("theme", "upload", "auto", "network")

HERO_AUTO_PERIODS = ("daily", "weekly", "random")

HERO_NETWORK_SOURCES = ("unsplash",)

HERO_UPLOAD_DIR = os.path.join(
    os.path.dirname(__file__),
    "static",
    "uploads",
    "hero",
)

HERO_ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".webp"}

HERO_ALLOWED_VIDEO = {".mp4", ".webm"}


def get_hero_config(db=None):
    """
    读取 Hero 全部配置项。

    Tnine v2：
    - name 取消独立网站名，统一使用管理员昵称（空显示"空"）
    - slogan 使用管理员简介（bio）
    """

    profile = get_admin_profile(db)

    return {
        "name": profile["nickname"] or "空",
        "slogan": profile["bio"],
        "avatar": get_setting_value("hero_avatar", ""),
        "bg_mode": get_setting_value("hero_bg_mode", "theme"),
        "auto_period": get_setting_value("hero_auto_period", "daily"),
        "network_source": get_setting_value(
            "hero_network_source",
            "unsplash",
        ),
        "network_keyword": get_setting_value(
            "hero_network_keyword",
            "minimal",
        ),
        "network_period": get_setting_value(
            "hero_network_period",
            "24",
        ),
    }


# ============================================================
# 社交链接类型（Tnine v2：动态添加）
# ============================================================

SOCIAL_LINK_TYPES = [
    {
        "value": "github",
        "label": "GitHub",
        "icon": "github",
    },
    {
        "value": "csdn",
        "label": "CSDN",
        "icon": "csdn",
    },
    {
        "value": "wechat",
        "label": "微信",
        "icon": "wechat",
    },
    {
        "value": "qq",
        "label": "QQ",
        "icon": "qq",
    },
    {
        "value": "email",
        "label": "邮箱",
        "icon": "email",
    },
    {
        "value": "website",
        "label": "个人网站",
        "icon": "website",
    },
    {
        "value": "other",
        "label": "其他",
        "icon": "other",
    },
]


def get_hero_social_links(db):
    """
    获取 Hero 展示的社交链接（is_visible=True，按排序）。
    """

    return (
        db.query(SocialLink)
        .filter(SocialLink.is_visible.is_(True))
        .order_by(
            SocialLink.sort_order.asc(),
            SocialLink.id.asc(),
        )
        .all()
    )


def get_hero_tags(db):
    """
    获取 Hero 展示的标签（show_on_home=True，按排序）。
    """

    return (
        db.query(Tag)
        .filter(Tag.show_on_home.is_(True))
        .order_by(
            Tag.sort_order.asc(),
            Tag.id.asc(),
        )
        .all()
    )


def get_hero_background(db, cfg):
    """
    根据背景模式返回当前 Hero 背景渲染信息。

    返回 dict：
    - kind: none（跟随主题） / image / video / network
    - url: 资源路径（image/video）
    - title: 资源标题
    - network_url: 网络图库接口地址（kind=network 时）
    """

    mode = cfg.get("bg_mode", "theme")

    # 4.1 跟随网站主题：无需背景资源
    if mode == "theme":

        return {
            "kind": "none",
            "url": "",
            "title": "",
        }

    # 4.2 自定义上传背景：使用 is_active 资源
    if mode == "upload":

        bg = (
            db.query(HeroBackground)
            .filter(HeroBackground.is_active.is_(True))
            .first()
        )

        if bg:

            return {
                "kind": bg.kind,
                "url": bg.file_path,
                "title": bg.title,
            }

        return {
            "kind": "none",
            "url": "",
            "title": "",
        }

    # 4.3 自动切换背景：按周期从图片资源中选取
    if mode == "auto":

        backgrounds = (
            db.query(HeroBackground)
            .filter(HeroBackground.kind == "image")
            .order_by(
                HeroBackground.sort_order.asc(),
                HeroBackground.id.asc(),
            )
            .all()
        )

        if not backgrounds:

            return {
                "kind": "none",
                "url": "",
                "title": "",
            }

        period = cfg.get("auto_period", "daily") or "daily"

        if period == "random":

            bg = random.choice(backgrounds)

        elif period == "weekly":

            iso_year, iso_week, _ = datetime.now().isocalendar()

            bg = backgrounds[
                (iso_year * 100 + iso_week) % len(backgrounds)
            ]

        else:

            bg = backgrounds[
                datetime.now().toordinal() % len(backgrounds)
            ]

        return {
            "kind": bg.kind,
            "url": bg.file_path,
            "title": bg.title,
        }

    # 4.4 网络图库背景：接口占位实现，前端加载失败回退主题默认背景
    if mode == "network":

        keyword = (
            cfg.get("network_keyword", "minimal") or "minimal"
        ).strip()

        return {
            "kind": "network",
            "url": "",
            "title": keyword,
            "network_url": (
                "/api/hero/network-image"
                "?keyword=" + quote(keyword)
            ),
        }

    return {
        "kind": "none",
        "url": "",
        "title": "",
    }


def get_admin_profile(db=None):
    """
    读取管理员资料（昵称/简介/邮箱），用于全站名称与 slogan。
    昵称为空时返回 ""（显示"空"），不使用默认昵称。
    """

    session_local = db if db is not None else SessionLocal()

    try:

        admin = (
            session_local.query(Admin)
            .order_by(Admin.id.asc())
            .first()
        )

        if admin is None:

            return {
                "nickname": "",
                "bio": "",
                "email": "",
                "avatar": get_setting_value("hero_avatar", ""),
            }

        return {
            "nickname": admin.nickname or "",
            "bio": admin.bio or "",
            "email": admin.email or "",
            "avatar": get_setting_value("hero_avatar", ""),
        }

    finally:

        if db is None:

            session_local.close()


def get_common_context(request: Request):
    """
    全站公共上下文。
    - site_name：网站核心名称 = 管理员昵称（空显示"空"）
    - site_logo：有头像用头像，无头像用昵称首字母
    """

    profile = get_admin_profile()

    nickname = profile["nickname"] or ""

    site_logo_text = (
        (nickname or "空")[0].upper()
        if nickname
        else "T"
    )

    # 页面信息：按当前路径选择对应页面标题与说明
    # （首页 / 文章 / 朋友圈 / 留言，来自网站设置卡片 8 字段）
    page_info = get_page_info()

    path = request.url.path.rstrip("/") or "/"

    if path.startswith("/articles"):
        page_key = "article"
    elif path.startswith("/moments"):
        page_key = "moment"
    elif path.startswith("/messages"):
        page_key = "message"
    else:
        page_key = "home"

    page_title = (
        page_info.get(page_key + "_title")
        or nickname
        or "空"
    )

    page_description = (
        page_info.get(page_key + "_description")
        or profile["bio"]
        or ""
    )

    return {
        "is_admin": is_admin(request),
        "admin_username": request.session.get(
            "admin_username"
        ),
        "admin_nickname": request.session.get(
            "admin_nickname",
            "",
        ),
        "site_name": nickname or "空",
        "site_bio": profile["bio"],
        "site_logo_text": site_logo_text,
        "site_primary_color": get_setting_value(
            "site_primary_color",
            "",
        ),
        "site_font": get_setting_value(
            "site_font",
            "default",
        ),
        "visitor_id": get_visitor_id(request),
        "theme": get_site_theme(),
        "site_avatar": profile["avatar"],
        "page_title": page_title,
        "page_description": page_description,
    }


# ============================================================
# 页面信息配置（网站设置卡片 8 字段）
# ============================================================

def get_page_info():
    """
    读取页面信息配置：home / article / moment / message
    各 title + description，共 8 字段。
    """

    keys = [
        "home_title",
        "home_description",
        "article_title",
        "article_description",
        "moment_title",
        "moment_description",
        "message_title",
        "message_description",
    ]

    info = {}

    for key in keys:
        info[key] = get_setting_value(key, "")

    return info


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
    request: Request | None = None,
):
    """
    确保 Visitor 档案存在（首次互动时自动建档）。

    已存在则更新昵称快照与最后活动时间。

    Tnine v2：新访客建档时写入 visitor 通知（管理员自身互动不计）。
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

        # 新访客通知（管理员自身互动不通知）
        if (
            request is not None
            and not is_admin(request)
        ):

            notifications_service.create_notification(
                db,
                type="visitor",
                target_id=0,
                content=(
                    f"新访客「{visitor.nickname}」访问了你的网站"
                ),
            )

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

    # 管理员：使用管理员昵称（Tnine v2 取消默认昵称，为空时返回 None）
    if is_admin(request):

        nickname = request.session.get(
            "admin_nickname",
            "",
        )

        return nickname or None, visitor_id

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
                selectinload(Article.tags),
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


        # 按时间倒序（文章优先使用首次发布时间 published_at）
        timeline.sort(
            key=lambda x: (
                x["data"].published_at
                if x["type"] == "article"
                else x["data"].created_at
            ) or x["data"].created_at,
            reverse=True
        )


        context = get_common_context(request)

        context["timeline"] = timeline

        context["threads"] = visible_threads

        context["liked_moment_ids"] = get_liked_moment_ids(
            db,
            get_visitor_id(request),
        )

        # ==========================
        # Hero 首屏数据
        # ==========================

        hero_cfg = get_hero_config()

        context["hero"] = {
            "name": hero_cfg["name"],
            "slogan": hero_cfg["slogan"],
            "avatar": hero_cfg["avatar"],
            "bg_mode": hero_cfg["bg_mode"],
            "bg": get_hero_background(db, hero_cfg),
            "tags": get_hero_tags(db),
            "social_links": get_hero_social_links(db),
        }


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
                selectinload(Article.tags),
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
# 需求：
# - 账号固定 admin，无注册入口
# - admin 不存在时进入初始化状态：生成初始密码 + 一次性初始化验证码，
#   登录页自动填充，用户无需输入账号/邮箱
# - admin 已存在时进入正常登录：密码 + 邮箱验证码
# ============================================================

@app.get("/admin/login")
def admin_login_page(
    request: Request,
):

    # 已经登录
    if not is_admin(request):

        db = SessionLocal()

        try:

            context = get_common_context(request)

            context["error"] = None

            init_state = get_admin_init_state()

            if init_state is not None:

                # 初始化模式：自动填充初始密码与初始化验证码
                context["need_initialization"] = True

                context["initial_password"] = (
                    init_state["password"]
                )

                context["initial_code"] = (
                    init_state["code"]
                )

            else:

                # 正常登录模式
                context["need_initialization"] = False

                context["mail_to"] = get_mail_config(
                    db
                )["to_addr"]

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
# GUEST：管理员登录提交
# mode=init   ：首次初始化登录（初始密码 + 一次性初始化验证码）
# mode=normal ：正常登录（正式密码 + 邮箱验证码）
# ============================================================

@app.post("/admin/login")
def admin_login(
    request: Request,
    mode: str = Form("normal"),
    password: str = Form(...),
    code: str = Form(...),
):

    if not is_admin(request):

        db = SessionLocal()

        try:

            if mode == "init":

                return _handle_init_login(
                    request, db, password, code,
                )

            return _handle_normal_login(
                request, db, password, code,
            )

        finally:

            db.close()

    return RedirectResponse(
        url="/admin",
        status_code=303,
    )


def _handle_init_login(
    request: Request,
    db,
    password: str,
    code: str,
):
    """
    首次初始化登录：
    - 初始密码正确 + 一次性初始化验证码正确 → 登录成功
    - 登录成功创建 admin 记录（password_hash=初始密码Hash），
      初始密码即正式密码，初始化验证码立即失效
    """

    init_state = get_admin_init_state()

    if init_state is None:

        context = get_common_context(request)

        context["error"] = "系统已完成初始化，请使用正式密码登录"

        context["need_initialization"] = False

        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context=context,
        )

    password_valid = password_hasher.verify(
        password,
        init_state["password_hash"],
    )

    code_valid = password_hasher.verify(
        code.strip(),
        init_state["code_hash"],
    )

    if not (password_valid and code_valid):

        context = get_common_context(request)

        context["error"] = "初始密码或初始化验证码不正确"

        context["need_initialization"] = True

        context["initial_password"] = (
            init_state["password"]
        )

        context["initial_code"] = (
            init_state["code"]
        )

        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context=context,
        )

    # 创建 admin 记录：初始密码直接成为正式密码（Hash 存储）
    # Tnine v2：取消默认昵称，nickname 为空字符串，首次登录后强制完善资料
    admin = Admin(
        username="admin",
        password_hash=init_state["password_hash"],
        nickname="",
    )

    db.add(admin)

    db.commit()

    db.refresh(admin)

    # 初始化验证码立即失效，不可再次使用
    clear_admin_init_state()

    print(
        "[Tnine] 管理员账号初始化完成：admin（初始密码已作为正式密码）"
    )

    _create_admin_session(request, admin)

    return RedirectResponse(
        url="/admin",
        status_code=303,
    )


def _handle_normal_login(
    request: Request,
    db,
    password: str,
    code: str,
):
    """
    正常登录：管理员密码 + 邮箱验证码。
    """

    admin = (
        db.query(Admin)
        .filter(
            Admin.username == "admin"
        )
        .first()
    )

    if admin is None:

        context = get_common_context(request)

        context["error"] = "管理员账号尚未初始化"

        context["need_initialization"] = True

        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context=context,
        )

    password_valid = password_hasher.verify(
        password,
        admin.password_hash,
    )

    code_valid = verify_login_code(code)

    if not (password_valid and code_valid):

        context = get_common_context(request)

        context["error"] = (
            "密码或邮箱验证码错误"
            if not code_valid
            else "密码错误"
        )

        context["need_initialization"] = False

        context["mail_to"] = get_mail_config(
            db
        )["to_addr"]

        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context=context,
        )

    _create_admin_session(request, admin)

    return RedirectResponse(
        url="/admin",
        status_code=303,
    )


def _create_admin_session(
    request: Request,
    admin,
):
    """
    创建管理员 Session 登录状态。
    """

    request.session["admin_id"] = admin.id

    request.session["admin_username"] = admin.username

    request.session["admin_nickname"] = (
        admin.nickname or ""
    )


# ============================================================
# GUEST：发送登录邮箱验证码
# 说明：登录前即可获取验证码（无需登录态）；
# 开发模式无 SMTP 配置时在日志/响应中提示验证码，便于本地联调
# ============================================================

@app.post("/admin/login/send-code")
def admin_send_login_code(
    request: Request,
):

    if is_admin(request):

        return JSONResponse(
            status_code=400,
            content={"ok": False, "detail": "已登录，无需验证码"},
        )

    db = SessionLocal()

    try:

        result = send_admin_login_code(db)

        return JSONResponse(
            content={
                "ok": result["ok"],
                "detail": (
                    result["reason"]
                    if not result["ok"]
                    else "验证码已发送，请查收邮箱"
                ),
                "dev_code": result["dev_code"],
            }
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：邮箱配置（后台）
# 配置 SMTP 发件邮箱 + 管理员收件邮箱，用于发送登录验证码
# ============================================================

@app.get("/admin/settings/email")
def admin_email_settings_page(
    request: Request,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        config = get_mail_config(db)

        context = get_common_context(request)

        context["config"] = config

        context["has_saved_password"] = bool(
            _get_setting_value(
                db, EMAIL_SMTP_PASSWORD_ENC_KEY, "",
            )
        )

        context["error"] = None

        context["notice"] = None

        return templates.TemplateResponse(
            request=request,
            name="admin_email_settings.html",
            context=context,
        )

    finally:

        db.close()


@app.post("/admin/settings/email")
def admin_email_settings_save(
    request: Request,
    smtp_host: str = Form(""),
    smtp_port: str = Form("465"),
    smtp_username: str = Form(""),
    smtp_password: str = Form(""),
    use_tls: str = Form("1"),
    from_addr: str = Form(""),
    to_addr: str = Form(""),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        smtp_host = smtp_host.strip()

        smtp_username = smtp_username.strip()

        from_addr = from_addr.strip()

        to_addr = to_addr.strip()

        try:
            smtp_port = int(smtp_port)
        except (TypeError, ValueError):
            smtp_port = 465

        if not smtp_host or not smtp_username or not from_addr:

            context = get_common_context(request)

            context["config"] = get_mail_config(db)

            context["has_saved_password"] = bool(
                _get_setting_value(
                    db, EMAIL_SMTP_PASSWORD_ENC_KEY, "",
                )
            )

            context["error"] = (
                "SMTP 主机、发件邮箱（SMTP 用户名）、发件人地址为必填项"
            )

            context["notice"] = None

            return templates.TemplateResponse(
                request=request,
                name="admin_email_settings.html",
                context=context,
            )

        _set_setting_value(db, EMAIL_SMTP_HOST_KEY, smtp_host)

        _set_setting_value(db, EMAIL_SMTP_PORT_KEY, str(smtp_port))

        _set_setting_value(db, EMAIL_SMTP_USERNAME_KEY, smtp_username)

        _set_setting_value(db, EMAIL_FROM_KEY, from_addr)

        _set_setting_value(db, EMAIL_TO_KEY, to_addr)

        _set_setting_value(
            db, EMAIL_USE_TLS_KEY,
            "1" if use_tls == "1" else "0",
        )

        # 邮箱密码：仅当填写了新密码时才更新（留空表示保持不变），
        # 加密存储，禁止明文落库
        if smtp_password.strip():

            _set_setting_value(
                db,
                EMAIL_SMTP_PASSWORD_ENC_KEY,
                encrypt_secret(smtp_password.strip()),
            )

        # 管理员收件邮箱同步到 Admin.email 字段
        admin = (
            db.query(Admin)
            .filter(Admin.id == request.session["admin_id"])
            .first()
        )

        if admin is not None:
            admin.email = to_addr or from_addr or None

        db.commit()

        return RedirectResponse(
            url="/admin/settings/email",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：管理员主页（Dashboard 卡片工作台）
# Tnine v2：纯卡片布局，无左侧/右侧导航
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

        # ====================================================
        # 首次登录强制完善资料：昵称为空时进入个人资料页
        # ====================================================

        admin = (
            db.query(Admin)
            .order_by(Admin.id.asc())
            .first()
        )

        if (
            admin is None
            or not (admin.nickname or "").strip()
        ):

            return RedirectResponse(
                url="/admin/profile?first=1",
                status_code=303,
            )


        context = get_common_context(request)

        # ---------- 文章卡片 ----------
        article_stats = (
            db.query(
                func.count(Article.id),
                func.coalesce(
                    func.sum(Article.views),
                    0,
                ),
            )
            .first()
        )

        context["article_count"] = (
            article_stats[0] or 0
        )

        context["article_views"] = (
            article_stats[1] or 0
        )

        context["article_likes"] = (
            db.query(ArticleLike)
            .count()
        )

        context["article_comments"] = (
            db.query(ArticleComment)
            .count()
        )

        # ---------- 朋友圈卡片 ----------
        context["moment_count"] = (
            db.query(Moment)
            .count()
        )

        context["moment_likes"] = (
            db.query(MomentLike)
            .count()
        )

        context["moment_comments"] = (
            db.query(MomentComment)
            .count()
        )

        # ---------- 留言卡片 ----------
        context["thread_count"] = (
            db.query(MessageThread)
            .count()
        )

        # 未回复：该会话最后一条消息为访客发送
        from sqlalchemy import text

        unreplied = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM message_threads t
                WHERE (
                    SELECT m.sender_type
                    FROM message m
                    WHERE m.thread_id = t.id
                    ORDER BY m.created_at DESC, m.id DESC
                    LIMIT 1
                ) = 'visitor'
                """
            )
        ).scalar() or 0

        context["unreplied_count"] = (
            unreplied
        )

        # ---------- 访客卡片 ----------
        context["visitor_count"] = (
            db.query(Visitor)
            .count()
        )

        today_start = datetime.now().replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        context["visitor_today"] = (
            db.query(Visitor)
            .filter(
                Visitor.created_at >= today_start
            )
            .count()
        )

        # ---------- 通知卡片 ----------
        context["notification_unread"] = (
            db.query(Notification)
            .filter(
                Notification.is_read.is_(False)
            )
            .count()
        )

        context["notification_latest"] = (
            db.query(Notification)
            .order_by(
                Notification.created_at.desc(),
                Notification.id.desc(),
            )
            .first()
        )


        return templates.TemplateResponse(
            request=request,
            name="admin_home.html",
            context=context,
        )

    finally:
        db.close()


# ============================================================
# AUTHENTICATED：文章管理列表（列表页即管理页）
# ============================================================

@app.get("/admin/articles")
def admin_articles_page(
    request: Request,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        articles = (
            db.query(Article)
            .options(
                selectinload(Article.tags),
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

        context["article_count"] = len(articles)

        # 是否有草稿（新建文章流程提示）
        context["has_draft"] = any(
            not a.published_at
            for a in articles
        )

        return templates.TemplateResponse(
            request=request,
            name="admin_articles.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：朋友圈管理列表
# ============================================================

@app.get("/admin/moments")
def admin_moments_page(
    request: Request,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


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

        context["moment_count"] = len(moments)

        return templates.TemplateResponse(
            request=request,
            name="admin_moments.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：留言管理列表
# ============================================================

@app.get("/admin/messages")
def admin_messages_page(
    request: Request,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )


    db = SessionLocal()

    try:

        threads = (
            db.query(MessageThread)
            .options(
                selectinload(
                    MessageThread.messages
                )
            )
            .order_by(
                MessageThread.updated_at.desc()
            )
            .all()
        )

        context = get_common_context(request)

        context["threads"] = threads

        context["thread_count"] = len(threads)

        # 未回复统计
        unreplied = 0

        for t in threads:

            last = (
                t.messages[-1]
                if t.messages
                else None
            )

            if (
                last is not None
                and last.sender_type == "visitor"
            ):

                unreplied += 1

        context["unreplied_count"] = unreplied

        return templates.TemplateResponse(
            request=request,
            name="admin_messages.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：管理员个人资料（基础资料 / 安全 / 社交链接）
# Tnine v2：卡片式个人资料页
# ============================================================

@app.get("/admin/profile")
def admin_profile_page(
    request: Request,
    first: int = 0,
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

        context["social_links"] = (
            db.query(SocialLink)
            .order_by(
                SocialLink.id.asc()
            )
            .all()
        )

        context["social_link_types"] = (
            SOCIAL_LINK_TYPES
        )

        context["avatar_url"] = get_setting_value(
            "hero_avatar",
            "",
        )

        # 首次登录强制完善资料标志
        context["first_login"] = bool(
            first == 1
            and not (admin.nickname or "").strip()
        )

        context["error"] = None

        return templates.TemplateResponse(
            request=request,
            name="admin_profile.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：保存管理员基础资料（昵称 / 简介 / 头像）
# ============================================================

@app.post("/admin/profile")
async def admin_profile_save(
    request: Request,
    nickname: str = Form(""),
    bio: str = Form(""),
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

            context["error"] = "昵称不能为空（昵称是全站核心名称）"

            context["social_links"] = (
                db.query(SocialLink)
                .order_by(SocialLink.id.asc())
                .all()
            )

            context["social_link_types"] = (
                SOCIAL_LINK_TYPES
            )

            context["avatar_url"] = get_setting_value(
                "hero_avatar",
                "",
            )

            context["first_login"] = False

            return templates.TemplateResponse(
                request=request,
                name="admin_profile.html",
                context=context,
            )

        first_time_complete = not (
            admin.nickname or ""
        ).strip()

        admin.nickname = nickname

        admin.bio = (bio or "").strip()[:200]

        # 头像上传（可选）
        form = await request.form()

        avatar_file = form.get("avatar")

        if (
            avatar_file
            and getattr(avatar_file, "filename", "")
        ):

            filename = avatar_file.filename or ""

            ext = os.path.splitext(filename)[1].lower()

            if ext not in HERO_ALLOWED_IMAGE:

                return RedirectResponse(
                    url="/admin/profile?error=avatar-format",
                    status_code=303,
                )

            os.makedirs(HERO_UPLOAD_DIR, exist_ok=True)

            save_name = (
                "avatar_"
                + uuid.uuid4().hex[:12]
                + ext
            )

            save_path = os.path.join(
                HERO_UPLOAD_DIR,
                save_name,
            )

            content = await avatar_file.read()

            with open(save_path, "wb") as f:

                f.write(content)

            set_setting_value(
                "hero_avatar",
                "/static/uploads/hero/" + save_name,
            )

        db.commit()

        # 同步会话昵称
        request.session["admin_nickname"] = nickname

        # 首次登录完善资料后直接进入后台首页
        return RedirectResponse(
            url=(
                "/admin"
                if first_time_complete
                else "/admin/profile"
            ),
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：修改管理员密码
# ============================================================

@app.post("/admin/profile/password")
def admin_profile_password_save(
    request: Request,
    old_password: str = Form(""),
    new_password: str = Form(""),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    if len(new_password) < 6:

        return RedirectResponse(
            url="/admin/profile?error=password-too-short",
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

        if not password_hasher.verify(
            old_password,
            admin.password_hash,
        ):

            return RedirectResponse(
                url="/admin/profile?error=password-wrong",
                status_code=303,
            )

        admin.password_hash = password_hasher.hash(
            new_password
        )

        db.commit()

        return RedirectResponse(
            url="/admin/profile?ok=password-changed",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：社交链接动态添加
# Tnine v2：选择类型 → 链接或二维码 → 生成图标与默认名称
# ============================================================

@app.post("/admin/profile/social")
async def admin_profile_social_add(
    request: Request,
    link_type: str = Form("github"),
    name: str = Form(""),
    link_value: str = Form(""),
    show_mode: str = Form("link"),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        type_cfg = next(
            (
                t
                for t in SOCIAL_LINK_TYPES
                if t["value"] == link_type
            ),
            SOCIAL_LINK_TYPES[0],
        )

        # 默认名称：类型标签；用户填写则使用用户名称
        link_name = (
            (name or "").strip()[:50]
            or type_cfg["label"]
        )

        link_value = (link_value or "").strip()[:500]

        if show_mode == "qr":

            # 二维码：解析上传二维码图片
            form = await request.form()

            qr_file = form.get("qr_code")

            qr_url = ""

            if (
                qr_file
                and getattr(qr_file, "filename", "")
            ):

                filename = qr_file.filename or ""

                ext = os.path.splitext(filename)[1].lower()

                if ext not in HERO_ALLOWED_IMAGE:

                    return RedirectResponse(
                        url="/admin/profile?error=qr-format",
                        status_code=303,
                    )

                os.makedirs(
                    HERO_UPLOAD_DIR,
                    exist_ok=True,
                )

                save_name = (
                    "qr_"
                    + uuid.uuid4().hex[:12]
                    + ext
                )

                save_path = os.path.join(
                    HERO_UPLOAD_DIR,
                    save_name,
                )

                content = await qr_file.read()

                with open(save_path, "wb") as f:

                    f.write(content)

                qr_url = (
                    "/static/uploads/hero/" + save_name
                )

            link = SocialLink(
                name=link_name,
                icon=type_cfg["icon"],
                url=link_value,
                is_visible=True,
                sort_order=0,
                link_type=link_type,
                qr_code=qr_url or None,
            )

            db.add(link)

            db.commit()

        else:

            if not link_value:

                return RedirectResponse(
                    url="/admin/profile?error=link-empty",
                    status_code=303,
                )

            link = SocialLink(
                name=link_name,
                icon=type_cfg["icon"],
                url=link_value,
                is_visible=True,
                sort_order=0,
                link_type=link_type,
                qr_code=None,
            )

            db.add(link)

            db.commit()

        return RedirectResponse(
            url="/admin/profile",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：社交链接显示切换
# ============================================================

@app.post("/admin/profile/social/{link_id}/toggle")
def admin_profile_social_toggle(
    request: Request,
    link_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        link = (
            db.query(SocialLink)
            .filter(SocialLink.id == link_id)
            .first()
        )

        if link is not None:

            link.is_visible = (
                not link.is_visible
            )

            db.commit()

        return RedirectResponse(
            url="/admin/profile",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：社交链接删除
# ============================================================

@app.post("/admin/profile/social/{link_id}/delete")
def admin_profile_social_delete(
    request: Request,
    link_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        link = (
            db.query(SocialLink)
            .filter(SocialLink.id == link_id)
            .first()
        )

        if link is not None:

            db.delete(link)

            db.commit()

        return RedirectResponse(
            url="/admin/profile",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：通知中心
# Tnine v2：7 类通知（article_like/article_comment/moment_like/
# moment_comment/message/message_reply/visitor）
# ============================================================

@app.get("/admin/notifications")
def admin_notifications_page(
    request: Request,
    scope: str = "all",
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        q = db.query(Notification)

        if scope == "unread":

            q = q.filter(
                Notification.is_read.is_(False)
            )

        notifications = (
            q.order_by(
                Notification.created_at.desc(),
                Notification.id.desc(),
            )
            .all()
        )

        context = get_common_context(request)

        context["notifications"] = notifications

        context["scope"] = scope

        context["unread_count"] = (
            db.query(Notification)
            .filter(
                Notification.is_read.is_(False)
            )
            .count()
        )

        return templates.TemplateResponse(
            request=request,
            name="admin_notifications.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：标记单条通知已读
# ============================================================

@app.post("/admin/notifications/{notification_id}/read")
def admin_notification_read(
    request: Request,
    notification_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        notification = (
            db.query(Notification)
            .filter(
                Notification.id == notification_id
            )
            .first()
        )

        if notification is not None:

            notification.is_read = True

            db.commit()

        return RedirectResponse(
            url="/admin/notifications",
            status_code=303,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：全部标记已读
# ============================================================

@app.post("/admin/notifications/read-all")
def admin_notifications_read_all(
    request: Request,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        (
            db.query(Notification)
            .filter(
                Notification.is_read.is_(False)
            )
            .update(
                {
                    "is_read": True
                },
                synchronize_session=False,
            )
        )

        db.commit()

        return RedirectResponse(
            url="/admin/notifications",
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
    force: int = 0,
):
    """
    新建文章页面。

    使用统一编辑器：
    article = None

    Tnine v2 草稿检测流程：
    - 无草稿 → 直接进入新增页
    - 有草稿 → 展示"发现已有草稿 [查看草稿] [新文章]"确认页
      （force=1 跳过提示，直接进入新增页）
    """

    if require_admin(request) is None:
        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    context = get_common_context(request)

    db = SessionLocal()

    try:

        drafts = (
            db.query(Article)
            .filter(
                Article.published_at.is_(None)
            )
            .order_by(
                Article.created_at.desc()
            )
            .all()
        )

        if (
            drafts
            and force != 1
        ):

            context["drafts"] = drafts

            return templates.TemplateResponse(
                request=request,
                name="admin_new_article_confirm.html",
                context=context,
            )

        context["article"] = None

        # 标签选择器数据
        context["all_tags"] = (
            db.query(Tag)
            .order_by(
                Tag.sort_order.asc(),
                Tag.id.asc(),
            )
            .all()
        )

        context["article_tag_ids"] = []

    finally:

        db.close()

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
    tag_ids: list[int] = Form([]),
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
            # 首次发布时生成发布时间；草稿不生成
            published_at=(
                datetime.now()
                if status == "published"
                else None
            ),
        )

        db.add(article)

        db.commit()

        db.refresh(article)


        # ====================================================
        # 关联标签
        # ====================================================

        if tag_ids:

            tags = (
                db.query(Tag)
                .filter(Tag.id.in_(tag_ids))
                .all()
            )

            article.tags = tags

            db.commit()


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

        # 标签选择器数据
        context["all_tags"] = (
            db.query(Tag)
            .order_by(
                Tag.sort_order.asc(),
                Tag.id.asc(),
            )
            .all()
        )

        context["article_tag_ids"] = [
            t.id for t in article.tags
        ]

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
    tag_ids: list[int] = Form([]),
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
        # 同步标签关联
        # ====================================================

        if tag_ids:

            tags = (
                db.query(Tag)
                .filter(Tag.id.in_(tag_ids))
                .all()
            )

            article.tags = tags

        else:

            article.tags = []


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

        # 发布时间规则：published_at 仅首次发布时生成，
        # 之后修改文章发布时间保持不变（created_at 也不再更新）
        if article.published_at is None:

            article.published_at = datetime.now()

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
# AUTHENTICATED：文章图片上传
# 供 EasyMDE 编辑器插入正文使用；返回 JSON 给前端回填 Markdown
# ============================================================

ARTICLE_IMAGE_DIR = "static/uploads/articles"

ALLOWED_ARTICLE_IMAGE_EXT = (
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp",
    "bmp",
)


@app.post("/admin/upload_image")
async def admin_upload_image(
    request: Request,
    image: UploadFile = File(...),
):

    if require_admin(request) is None:

        return JSONResponse(
            status_code=403,
            content={"success": False, "error": "无权操作"},
        )


    try:

        # 清理文件名，防止路径穿透
        original_name = os.path.basename(
            image.filename or ""
        )

        ext = original_name.lower().rsplit(".", 1)[-1] if "." in original_name else ""

        if ext not in ALLOWED_ARTICLE_IMAGE_EXT:

            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "仅支持 jpg/jpeg/png/gif/webp/bmp 图片"},
            )

        # MIME 校验：伪造扩展名的文件会被拒绝
        if not (
            image.content_type
            and image.content_type.startswith("image/")
        ):

            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "文件类型不合法"},
            )

        # 单张图片大小限制 10MB
        image.file.seek(0, 2)

        file_size = image.file.tell()

        image.file.seek(0)

        if file_size > 10 * 1024 * 1024:

            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "图片不能超过 10MB"},
            )

        os.makedirs(
            ARTICLE_IMAGE_DIR,
            exist_ok=True,
        )

        filename = (
            f"{uuid.uuid4().hex}_"
            f"{original_name}"
        )

        save_path = os.path.join(
            ARTICLE_IMAGE_DIR,
            filename,
        )

        with open(
            save_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                image.file,
                buffer,
            )

        url = (
            "/static/uploads/articles/"
            + filename
        )

        return JSONResponse(
            content={
                "success": True,
                "url": url,
            },
        )

    except Exception as exc:

        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"上传失败: {exc}"},
        )


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

    context["moment"] = None


    return templates.TemplateResponse(
        request=request,
        name="moment_editor.html",
        context=context,
    )


# ============================================================
# AUTHENTICATED：编辑朋友圈
# ============================================================

@app.get("/admin/moment/{moment_id}/edit")
def edit_moment_page(
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
            .filter(Moment.id == moment_id)
            .first()
        )

        if moment is None:

            return RedirectResponse(
                url="/admin/moments",
                status_code=303,
            )

        context = get_common_context(request)

        context["moment"] = moment

        return templates.TemplateResponse(
            request=request,
            name="moment_editor.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：保存朋友圈编辑（仅内容，图片保留）
# ============================================================

@app.post("/admin/moment/{moment_id}/update")
def update_moment(
    request: Request,
    moment_id: int,
    content: str = Form(...),
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
            .filter(Moment.id == moment_id)
            .first()
        )

        if moment is not None:

            moment.content = content.strip()

            db.commit()

        return RedirectResponse(
            url="/admin/moments",
            status_code=303,
        )

    finally:

        db.close()



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
                "",
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

        ensure_visitor(db, visitor_id, actor_name, request)

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

        # 通知：朋友圈点赞
        if not is_admin(request):

            notifications_service.create_notification(
                db,
                type="moment_like",
                target_id=moment_id,
                content=f"{actor_name} 赞了你的朋友圈：{moment.content[:50]}",
            )

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

        ensure_visitor(db, visitor_id, actor_name, request)

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

        # 通知：朋友圈评论
        if not is_admin(request):

            notifications_service.create_notification(
                db,
                type="moment_comment",
                target_id=moment_id,
                content=f"{actor_name} 评论了你的朋友圈：{content[:50]}",
            )

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

        ensure_visitor(db, visitor_id, actor_name, request)

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

        # 通知：文章点赞
        if not is_admin(request):

            notifications_service.create_notification(
                db,
                type="article_like",
                target_id=article_id,
                content=f"{actor_name} 赞了你的文章",
            )

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

        ensure_visitor(db, visitor_id, actor_name, request)

        db.flush()


        comment = ArticleComment(
            article_id=article.id,
            visitor_id=visitor_id,
            nickname=actor_name,
            content=content,
            reply_to_id=reply_to_id,
        )

        db.add(comment)

        # 通知：文章评论
        if not is_admin(request):

            notifications_service.create_notification(
                db,
                type="article_comment",
                target_id=article_id,
                content=f"{actor_name} 评论了你的文章：{content[:50]}",
            )

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

        # ====================================================
        # 多标签筛选（AND 逻辑：文章必须同时包含所有选中标签）
        # 支持 /articles?tags=a,b 逗号分隔
        # ====================================================

        selected_tags: list[str] = []

        raw_tags = request.query_params.get("tags", "").strip()

        if raw_tags:

            selected_tags = [
                t.strip()
                for t in raw_tags.split(",")
                if t.strip()
            ]

        query = (
            db.query(Article)
            .options(
                selectinload(Article.likes),
                selectinload(Article.comments).selectinload(ArticleComment.reply_to),
                selectinload(Article.tags),
            )
            .order_by(
                func.coalesce(
                    Article.published_at,
                    Article.created_at,
                ).desc()
            )
        )

        if not is_admin(request):

            query = query.filter(
                Article.status == "published"
            )

        # 多标签 AND：文章必须同时包含所有选中标签。
        # 用 IN 子查询替代多次 JOIN，避免 article_tags 重复 JOIN 时
        # 列名歧义（ambiguous column name）且语义更清晰。
        if selected_tags:

            for tag_name in selected_tags:

                subq = (
                    db.query(ArticleTag.article_id)
                    .join(
                        Tag,
                        Tag.id == ArticleTag.tag_id,
                    )
                    .filter(
                        Tag.name == tag_name
                    )
                )

                query = query.filter(
                    Article.id.in_(subq)
                )

        articles = query.all()

        context = get_common_context(request)

        context["articles"] = articles

        context["all_tags"] = (
            db.query(Tag)
            .order_by(
                Tag.sort_order.asc(),
                Tag.id.asc(),
            )
            .all()
        )

        context["selected_tags"] = selected_tags

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
        ensure_visitor(db, visitor_id, actor_name, request)

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

        # 通知：新留言（仅访客留言时通知）
        if not is_admin(request):

            notifications_service.create_notification(
                db,
                type="message",
                target_id=thread.id,
                content=f"{actor_name} 给你留了一条新留言：{content[:50]}",
            )

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
        ensure_visitor(db, visitor_id, actor_name, request)

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

        # 通知：留言回复（仅访客回复时通知）
        if not is_admin(request):

            notifications_service.create_notification(
                db,
                type="message_reply",
                target_id=thread.id,
                content=f"{actor_name} 回复了你的留言：{content[:50]}",
            )

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


# ============================================================
# PUBLIC：网络图库背景占位接口
# 说明：
# - 需求 4.4 允许接口占位实现
# - 返回 302 重定向到免费图库（picsum.photos，按关键词生成稳定 seed）
# - 真实部署可替换为 Unsplash API 等实现
# - 前端加载失败时回退主题默认背景，不影响页面加载速度
# ============================================================

@app.get("/api/hero/network-image")
def hero_network_image(
    keyword: str = "minimal",
):

    seed = hashlib.md5(
        keyword.encode("utf-8")
    ).hexdigest()[:8]

    return RedirectResponse(
        url=f"https://picsum.photos/seed/{seed}/1600/900",
        status_code=302,
    )


# ============================================================
# AUTHENTICATED：首页设置（Hero 首屏）
# ============================================================

@app.get("/admin/home")
def admin_home_settings_page(
    request: Request,
):

    if require_admin(request) is None:
        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        context = get_common_context(request)

        hero_cfg = get_hero_config(db)

        context["hero_cfg"] = hero_cfg

        context["backgrounds"] = (
            db.query(HeroBackground)
            .order_by(
                HeroBackground.sort_order.asc(),
                HeroBackground.id.asc(),
            )
            .all()
        )

        context["social_links"] = (
            db.query(SocialLink)
            .order_by(
                SocialLink.sort_order.asc(),
                SocialLink.id.asc(),
            )
            .all()
        )

        context["hero_bg_modes"] = HERO_BG_MODES

        context["hero_auto_periods"] = HERO_AUTO_PERIODS

        return templates.TemplateResponse(
            request=request,
            name="admin_home_settings.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：保存首页资料（昵称 / 个签 / 头像）
# ============================================================

@app.post("/admin/home/profile")
async def admin_home_profile_save(
    request: Request,
    hero_name: str = Form(""),
    hero_slogan: str = Form(""),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    # 保存昵称与个签
    set_setting_value(
        "hero_name",
        (hero_name or "").strip()[:50] or "Tnine",
    )

    set_setting_value(
        "hero_slogan",
        (hero_slogan or "").strip()[:200],
    )

    # 处理头像上传（可选）
    form = await request.form()

    avatar_file = form.get("avatar")

    if (
        avatar_file
        and getattr(avatar_file, "filename", "")
    ):

        filename = avatar_file.filename or ""

        ext = os.path.splitext(filename)[1].lower()

        if ext not in HERO_ALLOWED_IMAGE:

            return RedirectResponse(
                url="/admin/home?error=avatar-format",
                status_code=303,
            )

        os.makedirs(HERO_UPLOAD_DIR, exist_ok=True)

        save_name = (
            "avatar_"
            + uuid.uuid4().hex[:12]
            + ext
        )

        save_path = os.path.join(
            HERO_UPLOAD_DIR,
            save_name,
        )

        content = await avatar_file.read()

        with open(save_path, "wb") as f:

            f.write(content)

        set_setting_value(
            "hero_avatar",
            "/static/uploads/hero/" + save_name,
        )

    return RedirectResponse(
        url="/admin/home",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：上传 Hero 背景资源
# ============================================================

@app.post("/admin/home/background-upload")
async def admin_home_background_upload(
    request: Request,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    form = await request.form()

    bg_file = form.get("background_file")

    title = (
        form.get("background_title") or ""
    ).strip()[:100]

    if (
        not bg_file
        or not getattr(bg_file, "filename", "")
    ):

        return RedirectResponse(
            url="/admin/home?error=background-missing",
            status_code=303,
        )

    filename = bg_file.filename or ""

    ext = os.path.splitext(filename)[1].lower()

    if ext in HERO_ALLOWED_IMAGE:

        kind = "image"

    elif ext in HERO_ALLOWED_VIDEO:

        kind = "video"

    else:

        return RedirectResponse(
            url="/admin/home?error=background-format",
            status_code=303,
        )

    os.makedirs(HERO_UPLOAD_DIR, exist_ok=True)

    save_name = (
        "bg_"
        + uuid.uuid4().hex[:12]
        + ext
    )

    save_path = os.path.join(
        HERO_UPLOAD_DIR,
        save_name,
    )

    content = await bg_file.read()

    with open(save_path, "wb") as f:

        f.write(content)

    db = SessionLocal()

    try:

        bg = HeroBackground(
            kind=kind,
            source="upload",
            file_path="/static/uploads/hero/" + save_name,
            title=title or filename,
        )

        db.add(bg)

        db.commit()

        db.refresh(bg)

        # 首次上传自动设为当前背景
        active_count = (
            db.query(HeroBackground)
            .filter(HeroBackground.is_active.is_(True))
            .count()
        )

        if active_count == 0:

            bg.is_active = True

            db.commit()

    finally:

        db.close()

    return RedirectResponse(
        url="/admin/home",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：设为当前 Hero 背景
# ============================================================

@app.post("/admin/home/background/{bg_id}/activate")
def admin_home_background_activate(
    request: Request,
    bg_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        bg = (
            db.query(HeroBackground)
            .filter(HeroBackground.id == bg_id)
            .first()
        )

        if bg is None:

            return RedirectResponse(
                url="/admin/home",
                status_code=303,
            )

        # 清除旧的当前背景
        (
            db.query(HeroBackground)
            .filter(HeroBackground.is_active.is_(True))
            .update({"is_active": False})
        )

        bg.is_active = True

        db.commit()

    finally:

        db.close()

    return RedirectResponse(
        url="/admin/home",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：删除 Hero 背景资源
# ============================================================

@app.post("/admin/home/background/{bg_id}/delete")
def admin_home_background_delete(
    request: Request,
    bg_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        bg = (
            db.query(HeroBackground)
            .filter(HeroBackground.id == bg_id)
            .first()
        )

        if bg is None:

            return RedirectResponse(
                url="/admin/home",
                status_code=303,
            )

        # 删除磁盘文件（仅限 hero 上传目录内的资源）
        file_name = os.path.basename(
            bg.file_path or ""
        )

        if (
            file_name
            and (
                file_name.startswith("bg_")
                or file_name.startswith("avatar_")
            )
        ):

            disk_path = os.path.join(
                HERO_UPLOAD_DIR,
                file_name,
            )

            if os.path.exists(disk_path):

                os.remove(disk_path)

        db.delete(bg)

        db.commit()

    finally:

        db.close()

    return RedirectResponse(
        url="/admin/home",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：保存 Hero 背景设置（模式 / 自动切换 / 网络图库）
# ============================================================

@app.post("/admin/home/background-settings")
def admin_home_background_settings_save(
    request: Request,
    bg_mode: str = Form("theme"),
    auto_period: str = Form("daily"),
    network_source: str = Form("unsplash"),
    network_keyword: str = Form("minimal"),
    network_period: str = Form("24"),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    if bg_mode not in HERO_BG_MODES:

        bg_mode = "theme"

    if auto_period not in HERO_AUTO_PERIODS:

        auto_period = "daily"

    set_setting_value("hero_bg_mode", bg_mode)

    set_setting_value("hero_auto_period", auto_period)

    set_setting_value(
        "hero_network_source",
        network_source,
    )

    set_setting_value(
        "hero_network_keyword",
        (network_keyword or "").strip()[:50] or "minimal",
    )

    set_setting_value(
        "hero_network_period",
        (network_period or "").strip()[:10] or "24",
    )

    return RedirectResponse(
        url="/admin/home",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：新增社交链接
# ============================================================

@app.post("/admin/home/social")
def admin_home_social_create(
    request: Request,
    name: str = Form(...),
    icon: str = Form("link"),
    url: str = Form(""),
    sort_order: int = Form(0),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        link = SocialLink(
            name=(name or "").strip()[:50] or "链接",
            icon=(icon or "link").strip()[:30],
            url=(url or "").strip()[:500],
            sort_order=sort_order,
            is_visible=True,
        )

        db.add(link)

        db.commit()

    finally:

        db.close()

    return RedirectResponse(
        url="/admin/home",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：社交链接显示切换
# ============================================================

@app.post("/admin/home/social/{link_id}/toggle")
def admin_home_social_toggle(
    request: Request,
    link_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        link = (
            db.query(SocialLink)
            .filter(SocialLink.id == link_id)
            .first()
        )

        if link is not None:

            link.is_visible = not link.is_visible

            db.commit()

    finally:

        db.close()

    return RedirectResponse(
        url="/admin/home",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：删除社交链接
# ============================================================

@app.post("/admin/home/social/{link_id}/delete")
def admin_home_social_delete(
    request: Request,
    link_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        link = (
            db.query(SocialLink)
            .filter(SocialLink.id == link_id)
            .first()
        )

        if link is not None:

            db.delete(link)

            db.commit()

    finally:

        db.close()

    return RedirectResponse(
        url="/admin/home",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：网站设置卡片（外观 / 标签 / 页面信息）
# Tnine v2：卡片式配置
# ============================================================

@app.get("/admin/settings")
def admin_settings_page(
    request: Request,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        context = get_common_context(request)

        # ---------- 外观：Hero 配置摘要 ----------
        hero_cfg = get_hero_config(db)

        context["hero_cfg"] = hero_cfg

        context["hero_bg_modes"] = HERO_BG_MODES

        context["hero_auto_periods"] = (
            HERO_AUTO_PERIODS
        )

        context["background_count"] = (
            db.query(HeroBackground)
            .count()
        )

        # ---------- 标签 ----------
        tags = (
            db.query(Tag)
            .order_by(
                Tag.id.asc()
            )
            .all()
        )

        context["tags"] = tags

        # ---------- 页面信息 8 字段 ----------
        context["page_info"] = {
            "home_title": get_setting_value(
                "home_title", ""
            ),
            "home_description": get_setting_value(
                "home_description", ""
            ),
            "article_title": get_setting_value(
                "article_title", ""
            ),
            "article_description": get_setting_value(
                "article_description", ""
            ),
            "moment_title": get_setting_value(
                "moment_title", ""
            ),
            "moment_description": get_setting_value(
                "moment_description", ""
            ),
            "message_title": get_setting_value(
                "message_title", ""
            ),
            "message_description": get_setting_value(
                "message_description", ""
            ),
        }

        context["site_theme"] = get_site_theme()

        return templates.TemplateResponse(
            request=request,
            name="admin_settings.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：保存页面信息（8 字段）
# ============================================================

@app.post("/admin/settings/pages")
def admin_settings_pages_save(
    request: Request,
    home_title: str = Form(""),
    home_description: str = Form(""),
    article_title: str = Form(""),
    article_description: str = Form(""),
    moment_title: str = Form(""),
    moment_description: str = Form(""),
    message_title: str = Form(""),
    message_description: str = Form(""),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    for key, value in {
        "home_title": home_title,
        "home_description": home_description,
        "article_title": article_title,
        "article_description": article_description,
        "moment_title": moment_title,
        "moment_description": moment_description,
        "message_title": message_title,
        "message_description": message_description,
    }.items():

        set_setting_value(
            key,
            (value or "").strip()[:200],
        )

    return RedirectResponse(
        url="/admin/settings",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：保存外观设置（主色 / 字体）
# ============================================================

@app.post("/admin/settings/appearance")
def admin_settings_appearance_save(
    request: Request,
    primary_color: str = Form(""),
    font: str = Form(""),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    primary_color = (primary_color or "").strip()

    if primary_color:

        set_setting_value(
            "site_primary_color",
            primary_color[:30],
        )

    font = (font or "").strip()

    if font in {"default", "serif", "mono"}:

        set_setting_value(
            "site_font",
            font,
        )

    return RedirectResponse(
        url="/admin/settings",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：标签管理
# ============================================================

@app.get("/admin/tags")
def admin_tags_page(
    request: Request,
):

    if require_admin(request) is None:
        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        context = get_common_context(request)

        context["tags"] = (
            db.query(Tag)
            .order_by(
                Tag.sort_order.asc(),
                Tag.id.asc(),
            )
            .all()
        )

        # 每个标签关联的文章数
        context["tag_counts"] = {}

        for tag in context["tags"]:

            context["tag_counts"][tag.id] = (
                db.query(ArticleTag)
                .filter(ArticleTag.tag_id == tag.id)
                .count()
            )

        return templates.TemplateResponse(
            request=request,
            name="admin_tags.html",
            context=context,
        )

    finally:

        db.close()


# ============================================================
# AUTHENTICATED：创建标签
# ============================================================

@app.post("/admin/tags")
def admin_tag_create(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    sort_order: int = Form(0),
    show_on_home: str = Form(""),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    tag_name = (name or "").strip()[:50]

    if not tag_name:

        return RedirectResponse(
            url="/admin/tags?error=name-empty",
            status_code=303,
        )

    db = SessionLocal()

    try:

        exists = (
            db.query(Tag)
            .filter(Tag.name == tag_name)
            .first()
        )

        if exists is not None:

            return RedirectResponse(
                url="/admin/tags?error=duplicate",
                status_code=303,
            )

        tag = Tag(
            name=tag_name,
            description=(description or "").strip()[:200],
            sort_order=sort_order,
            show_on_home=(show_on_home == "on"),
        )

        db.add(tag)

        db.commit()

    finally:

        db.close()

    return RedirectResponse(
        url="/admin/tags",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：编辑标签
# ============================================================

@app.post("/admin/tags/{tag_id}/edit")
def admin_tag_edit(
    request: Request,
    tag_id: int,
    name: str = Form(...),
    description: str = Form(""),
    sort_order: int = Form(0),
    show_on_home: str = Form(""),
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    tag_name = (name or "").strip()[:50]

    if not tag_name:

        return RedirectResponse(
            url="/admin/tags?error=name-empty",
            status_code=303,
        )

    db = SessionLocal()

    try:

        tag = (
            db.query(Tag)
            .filter(Tag.id == tag_id)
            .first()
        )

        if tag is None:

            return RedirectResponse(
                url="/admin/tags",
                status_code=303,
            )

        duplicate = (
            db.query(Tag)
            .filter(
                Tag.name == tag_name,
                Tag.id != tag_id,
            )
            .first()
        )

        if duplicate is not None:

            return RedirectResponse(
                url="/admin/tags?error=duplicate",
                status_code=303,
            )

        tag.name = tag_name

        tag.description = (description or "").strip()[:200]

        tag.sort_order = sort_order

        tag.show_on_home = (show_on_home == "on")

        db.commit()

    finally:

        db.close()

    return RedirectResponse(
        url="/admin/tags",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：删除标签
# 删除仅移除标签本身与关联关系，不删除文章
# ============================================================

@app.post("/admin/tags/{tag_id}/delete")
def admin_tag_delete(
    request: Request,
    tag_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        tag = (
            db.query(Tag)
            .filter(Tag.id == tag_id)
            .first()
        )

        if tag is not None:

            # SQLite 未强制外键时先手动清理关联，避免残留
            db.query(ArticleTag).filter(
                ArticleTag.tag_id == tag.id
            ).delete(synchronize_session=False)

            db.delete(tag)

            db.commit()

    finally:

        db.close()

    return RedirectResponse(
        url="/admin/tags",
        status_code=303,
    )


# ============================================================
# AUTHENTICATED：标签首页展示切换
# ============================================================

@app.post("/admin/tags/{tag_id}/toggle")
def admin_tag_toggle(
    request: Request,
    tag_id: int,
):

    if require_admin(request) is None:

        return RedirectResponse(
            url="/admin/login",
            status_code=303,
        )

    db = SessionLocal()

    try:

        tag = (
            db.query(Tag)
            .filter(Tag.id == tag_id)
            .first()
        )

        if tag is not None:

            tag.show_on_home = not tag.show_on_home

            db.commit()

    finally:

        db.close()

    return RedirectResponse(
        url="/admin/tags",
        status_code=303,
    )


# ============================================================
# PUBLIC：标签筛选页 /tag/{tag_name}
# ============================================================

@app.get("/tag/{tag_name}")
def tag_detail_page(
    request: Request,
    tag_name: str,
):

    db = SessionLocal()

    try:

        tag = (
            db.query(Tag)
            .filter(Tag.name == tag_name)
            .first()
        )

        if tag is None:

            raise HTTPException(
                status_code=404,
                detail="标签不存在",
            )

        query = (
            db.query(Article)
            .join(ArticleTag, ArticleTag.article_id == Article.id)
            .filter(
                ArticleTag.tag_id == tag.id,
                Article.status == "published",
            )
            .options(
                selectinload(Article.likes),
                selectinload(Article.comments).selectinload(ArticleComment.reply_to),
                selectinload(Article.tags),
            )
            .order_by(
                func.coalesce(
                    Article.published_at,
                    Article.created_at,
                ).desc()
            )
        )

        articles = query.all()

        context = get_common_context(request)

        context["tag"] = tag

        context["articles"] = articles

        return templates.TemplateResponse(
            request=request,
            name="tag_detail.html",
            context=context,
        )

    finally:

        db.close()
