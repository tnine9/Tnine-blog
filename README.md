---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 253448c08a47e975e2eac8c2baf2d690_7eb53f6e9ee411f1a238525400e6dd8f
    ReservedCode1: xroPdwPACgfpz59GClq6n8aKgVPzfYFfTqH+chnvT7F1aFdMnNvh5J1fPGw4w9hgERLs3g2JZ2UuO2ZDjf41gXvS5i/PshDN4kZpA8t1OWjGxKrPjDzxdtblcuqNCtaOr6gol7aDSJDZ9M4Q/7dKS1Z0P5dgJ6UmQ/q4fdJNaMPifycTCXelNpf/Sio=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 253448c08a47e975e2eac8c2baf2d690_7eb53f6e9ee411f1a238525400e6dd8f
    ReservedCode2: xroPdwPACgfpz59GClq6n8aKgVPzfYFfTqH+chnvT7F1aFdMnNvh5J1fPGw4w9hgERLs3g2JZ2UuO2ZDjf41gXvS5i/PshDN4kZpA8t1OWjGxKrPjDzxdtblcuqNCtaOr6gol7aDSJDZ9M4Q/7dKS1Z0P5dgJ6UmQ/q4fdJNaMPifycTCXelNpf/Sio=
---

# Tnine 博客

一个轻量、开箱即用的个人博客系统，基于 **FastAPI + Jinja2 + SQLite** 构建，前端使用原生 HTML / CSS / JavaScript，无复杂构建工具。内置**文章、朋友圈、留言板**三大内容模块，并附带完整的后台管理系统、访客身份系统、标签体系、全站外观配置与 SMTP 邮件通知。

## 功能特性

### 内容模块
- **文章系统**：Markdown 写作、标签体系、草稿 / 发布、点赞 / 评论、浏览量统计、文章详情页 TOC 目录、代码块一键复制。
- **朋友圈**：图文动态、图片九宫格与大图查看、点赞 / 评论、发布 / 编辑 / 删除、独立详情页。
- **留言板**：留言 + 回复，访客无需注册即可参与互动。
- **首页时间线**：文章、朋友圈、留言按时间统一聚合展示，支持 Hero 首屏与平滑滚动导航。

### 后台管理（`/admin`）
- **仪表盘**：文章 / 朋友圈 / 留言 / 访客数据总览。
- **内容管理**：文章、朋友圈、留言的新增、编辑、删除。
- **访客管理**：查看访问记录与访客身份。
- **通知中心**：文章与朋友圈的点赞、评论、留言回复、新访客等 7 类通知。
- **标签管理**：增删标签，前台按标签筛选。
- **网站设置**：外观设置（明暗主题 / 主色 / 字体 / ICP）、页面信息（首页 / 文章 / 朋友圈 / 留言的标题与描述）、邮箱（SMTP）配置。
- **个人资料**：管理员昵称、简介、头像（全站头像统一来源）。

### 访客与身份
- 访客自动获得本地持久化的身份（昵称可修改），点赞、评论、留言无需注册。

### 安全与运维
- 邮箱验证码登录（6 位数字、5 分钟有效、一次性），账号固定为 `admin`，不可注册。
- 首次启动自动生成高强度随机初始密码 + 一次性初始化验证码，不硬编码、不落库。
- 密码使用 Argon2（`pwdlib`）哈希存储；Markdown 输出经 `nh3` 消毒防 XSS；Session Cookie 支持生产环境 `Secure` 属性。

## 技术栈

| 类别 | 技术 |
| --- | --- |
| 后端 | Python 3.11+ / FastAPI / Uvicorn |
| 模板 | Jinja2 |
| 数据库 | SQLAlchemy + SQLite（默认 `sqlite:///./blog.db`，可用环境变量覆盖） |
| 会话 | Starlette SessionMiddleware |
| 密码 | pwdlib（Argon2） |
| Markdown | python-markdown + nh3（HTML 消毒） |
| 图片 | Pillow（头像裁剪、图片处理） |
| 邮件 | smtplib（SMTP 验证码 / 通知） |
| 前端 | 原生 HTML / CSS / JavaScript（无框架、无构建步骤） |

## 目录结构

```
my-blog/
├── main.py                    # 应用入口与全部路由 / 业务逻辑（约 6400 行）
├── database.py                # SQLAlchemy 引擎与会话
├── models.py                  # ORM 数据模型（文章/朋友圈/留言/访客/设置/通知等）
├── notifications_service.py   # 通知服务（点赞/评论/留言/访客）
├── init_db.py                 # 可选：写入一篇测试文章
├── create_admin.py            # 可选：创建管理员账号脚本
├── migrate_*.py               # 历史数据迁移脚本
├── templates/                 # Jinja2 模板
│   ├── base.html              # 全局布局 / 导航 / 主题
│   ├── index.html             # 首页（Hero + 时间线）
│   ├── articles.html          # 文章列表
│   ├── article_detail.html    # 文章详情
│   ├── moments.html           # 朋友圈列表
│   ├── moment_detail.html     # 朋友圈详情
│   ├── moment_editor.html     # 朋友圈发布/编辑
│   ├── messages.html          # 留言板
│   ├── message_detail.html    # 留言详情
│   ├── timeline.html          # 时间线页
│   ├── tag_detail.html        # 标签归档页
│   ├── admin_*.html           # 后台管理页面
│   └── components/            # 可复用组件（文章/朋友圈/留言卡片等）
├── static/
│   ├── css/                   # 原生 CSS（variables/base/layout/components/article/moment 等）
│   ├── js/                    # 原生 JS（main/moment/modal 等）
│   └── fonts/                 # 字体资源
└── logs/                      # 运行日志（开发模式登录验证码写入 login_codes.log）
```

## 快速开始

### 环境要求
- Python 3.11 及以上
- pip

### 1. 安装依赖

```bash
cd my-blog
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install fastapi "uvicorn[standard]" jinja2 sqlalchemy pwdlib markdown nh3 pillow python-multipart
```

### 2. 启动

```bash
uvicorn main:app --reload --port 8000
```

首次启动会自动创建 SQLite 数据库与全部数据表（无需手动建库）。浏览器访问：

- 前台首页：<http://127.0.0.1:8000>
- 后台管理：<http://127.0.0.1:8000/admin>

> 可选：执行 `python init_db.py` 写入一篇测试文章，方便快速预览效果。

### 3. 初始化管理员（首次登录）

系统尚未创建管理员时，启动终端会打印：

```
[Tnine] 初始密码: X8kP29mQ7a
[Tnine] 初始化验证码: 739214
```

打开 `/admin/login`，页面会自动展示并填充**初始密码**与**一次性初始化验证码**，点击「完成初始化并登录」即可。初始密码即为正式密码；初始化验证码仅能使用一次。

首次登录后系统会引导完善个人资料（昵称等），完成后即可进入后台。

## 后台配置指南

### 日常登录

- 账号固定为 **admin**，无注册入口。
- 打开 `/admin/login`，输入密码后点击「获取验证码」。
- 验证码为 6 位数字，5 分钟内有效、一次性。
- 验证码发送方式：
  - 已配置 SMTP：发送到管理员收件邮箱；
  - 未配置 SMTP（开发模式）：直接打印在启动终端，同时写入 `logs/login_codes.log`。

### SMTP 邮箱配置

两种方式（后台配置优先于环境变量）：

**方式一：后台页面**
进入 `后台 → 网站设置 → 邮箱配置`，填写：

| 字段 | 说明 |
| --- | --- |
| SMTP 服务器 | 如 `smtp.qq.com` |
| SMTP 端口 | 如 `465` / `587` |
| 用户名 | SMTP 登录账号 |
| 密码 | SMTP 授权码 |
| 发件人 | 发件邮箱地址 |
| 收件人 | 管理员收件邮箱 |
| 启用 TLS | 按服务商要求勾选 |

保存后即可用邮箱接收登录验证码。

**方式二：环境变量**

```bash
export TNINE_SMTP_HOST=smtp.example.com
export TNINE_SMTP_PORT=465
export TNINE_SMTP_USERNAME=admin@example.com
export TNINE_MAIL_PASSWORD=your-smtp-auth-code
export TNINE_MAIL_FROM=Tnine <no-reply@example.com>
export TNINE_MAIL_TO=you@example.com
export TNINE_MAIL_SECRET_KEY=用于加密存储邮箱密码的密钥
```

### 全站主题 / 外观设置

进入 `后台 → 网站设置 → 外观设置`：

- **主题**：明 / 暗主题（前台右上角也可一键切换，选择对全站访客生效）。
- **主色**：自定义站点主色调。
- **字体**：默认 / 衬线 / 等宽。
- **ICP 备案号**：显示在页脚。

在 `后台 → 个人资料` 可设置管理员昵称、简介与**站点头像**（全站头像统一来源，含导航 / 页脚 / 朋友圈卡片）。

首页 Hero 首屏的展示名称、标语来自个人资料与网站设置，背景支持图片 / 视频，可在后台首页设置中调整。

### 页面标题与描述

`后台 → 网站设置 → 页面信息` 可分别配置首页、文章、朋友圈、留言页的标题与描述（对应前台各页面顶部标题区）。

## 环境变量

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `TNINE_DATABASE_URL` | 数据库连接串 | `sqlite:///./blog.db` |
| `TNINE_SECRET_KEY` | Session 签名密钥（生产环境务必修改为强随机值） | `Tnine-dev-secret-2026` |
| `TNINE_ENV` | 设为 `production` 时启用 Secure Cookie（需 HTTPS） | 空 |
| `TNINE_SMTP_HOST` / `TNINE_SMTP_PORT` / `TNINE_SMTP_USERNAME` | SMTP 服务器配置 | 空 |
| `TNINE_MAIL_PASSWORD` / `TNINE_MAIL_FROM` / `TNINE_MAIL_TO` | 邮件发送配置 | 空 |
| `TNINE_MAIL_SECRET_KEY` | 邮箱密码加密密钥 | 空 |
| `TNINE_ADMIN_PASSWORD` | `create_admin.py` 创建管理员时使用的密码（未设置则生成随机密码） | 空 |

## 常见问题

**Q1：首次启动没看到初始密码 / 初始化验证码？**
初始密码与验证码会打印在启动终端（stderr）。若已错过，直接访问 `/admin/login`，只要 `admins` 表仍为空，页面就会重新展示。

**Q2：登录验证码收不到邮件？**
未配置 SMTP 时处于开发模式，验证码会打印在终端并写入 `logs/login_codes.log`；配置 SMTP 后请检查服务器端口、授权码与 TLS 设置。

**Q3：如何修改数据库位置？**
通过 `TNINE_DATABASE_URL` 指定，例如 `sqlite:///D:/data/blog.db`。修改前请先停止服务并备份原数据库。

**Q4：生产环境部署要注意什么？**
- 设置 `TNINE_ENV=production`（HTTPS 下启用 Secure Cookie）；
- 设置强随机 `TNINE_SECRET_KEY`；
- 配置 SMTP 以便接收登录验证码；
- 首次初始化请保证单进程完成（多 worker 部署时先单进程初始化，再扩容）。

**Q5：忘记管理员密码怎么办？**
项目不提供自助找回。可备份数据库后，删除 `admins` 表中的记录并重启服务，系统将重新触发初始化流程生成新的初始密码；或使用 `python create_admin.py`（可通过 `TNINE_ADMIN_PASSWORD` 指定密码，但脚本不会覆盖已存在的 admin 账号）。

**Q6：如何修改端口？**
`uvicorn main:app --reload --port 8080`。

**Q7：`migrate_*.py` 脚本是什么？**
历史版本升级用的数据迁移脚本。正常使用无需手动执行；升级项目时可参考相应脚本说明。

## 许可证

本项目未附带开源许可证文件。如有使用、二次开发或分发需求，请先联系作者获取授权。
*（内容由AI生成，仅供参考）*
