/* ============================================================
   Tnine · Front-end Interactions
   ============================================================ */
(function () {
  "use strict";
  const T = window.Tnine;
  const MD = window.Markdown;

  /* ---------- Theme ---------- */
  function applyTheme(theme, primary) {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme === "dark" ? "dark" : "light");
    if (primary) {
      root.style.setProperty("--primary", primary);
      root.style.setProperty("--primary-grad", "linear-gradient(135deg, " + primary + " 0%, #7C6CF0 100%)");
    }
  }
  function initTheme() {
    const s = T.load().settings;
    let theme = s.theme;
    try { theme = localStorage.getItem("tnine_theme") || s.theme; } catch (e) {}
    applyTheme(theme, s.primaryColor);
    const btn = document.querySelector(".theme-toggle");
    if (btn) {
      btn.innerHTML = theme === "dark" ? "☀️" : "🌙";
      btn.onclick = function () {
        const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        applyTheme(cur, T.load().settings.primaryColor);
        try { localStorage.setItem("tnine_theme", cur); } catch (e) {}
        btn.innerHTML = cur === "dark" ? "☀️" : "🌙";
        toast("已切换为" + (cur === "dark" ? "暗色" : "亮色") + "主题");
      };
    }
  }

  /* ---------- Toast ---------- */
  function toast(msg, type) {
    let wrap = document.querySelector(".toast-wrap");
    if (!wrap) { wrap = document.createElement("div"); wrap.className = "toast-wrap"; document.body.appendChild(wrap); }
    const el = document.createElement("div");
    el.className = "toast " + (type || "success");
    el.innerHTML = msg;
    wrap.appendChild(el);
    setTimeout(function () { el.style.opacity = "0"; el.style.transition = "opacity .3s"; setTimeout(function () { el.remove(); }, 320); }, 2600);
  }
  window.toast = toast;

  /* ---------- Navbar ---------- */
  function initNav() {
    const nav = document.querySelector(".nav");
    if (nav) {
      window.addEventListener("scroll", function () {
        nav.classList.toggle("scrolled", window.scrollY > 12);
      }, { passive: true });
    }

    // mark active link
    const path = location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll(".nav-link").forEach(function (a) {
      const href = a.getAttribute("href");
      if (href === path || (path === "" && href === "index.html")) a.classList.add("active");
    });
    document.querySelectorAll(".bottom-nav a").forEach(function (a) {
      const href = a.getAttribute("href");
      if (href === path || (path === "" && href === "index.html")) a.classList.add("active");
    });

    // auth area
    const area = document.getElementById("nav-auth");
    if (area) {
      if (T.isLoggedIn()) {
        const u = T.currentUser();
        const s = T.load().settings;
        area.innerHTML =
          '<div class="nav-avatar-wrap">' +
          '<button class="avatar-btn" id="avatar-btn"><img class="nav-avatar" src="' + (s.avatar || T.svgAvatar("T", 0)) + '" alt="avatar"><span class="nav-user-name">' + (u.name || "Tnine") + '</span></button>' +
          '<div class="dropdown" id="dropdown">' +
          '<a class="dropdown-item" href="admin.html">📊 管理后台</a>' +
          '<a class="dropdown-item" href="messages.html">💬 留言板</a>' +
          '<div class="dropdown-sep"></div>' +
          '<div class="dropdown-item danger" id="logout-btn">⎋ 退出登录</div>' +
          '</div></div>';
        const btn = document.getElementById("avatar-btn");
        const dd = document.getElementById("dropdown");
        btn.addEventListener("click", function (e) { e.stopPropagation(); dd.classList.toggle("open"); });
        document.addEventListener("click", function (e) { if (!e.target.closest(".nav-avatar-wrap")) dd.classList.remove("open"); });
        document.getElementById("logout-btn").addEventListener("click", function () {
          T.logout(); toast("已退出登录"); setTimeout(function () { location.reload(); }, 600);
        });
      } else {
        area.innerHTML = '<a href="admin.html" class="btn btn-primary btn-sm">登录</a>';
      }
    }
  }

  /* ---------- Reveal on scroll ---------- */
  function initReveal() {
    const els = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) { els.forEach(function (el) { el.classList.add("in"); }); return; }
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { threshold: 0.08, rootMargin: "0px 0px -40px 0px" });
    els.forEach(function (el) { io.observe(el); });
  }

  /* ---------- Homepage timeline ---------- */
  function renderHomeTimeline() {
    const wrap = document.getElementById("timeline");
    if (!wrap) return;
    const d = T.load();
    const items = [];
    d.articles.filter(function (a) { return a.status === "published"; }).slice(0, 4).forEach(function (a) {
      items.push({ type: "article", date: a.date, title: a.title, desc: a.summary, href: "article.html?id=" + a.id, badge: "发表文章" });
    });
    d.moments.slice(0, 4).forEach(function (m) {
      items.push({ type: "moment", date: m.date, title: m.text.slice(0, 40), desc: m.text, href: "moments.html", badge: "朋友圈" });
    });
    d.messages.filter(function (m) { return !m.isPrivate; }).slice(0, 3).forEach(function (m) {
      items.push({ type: "message", date: m.date, title: m.nickname + " 的留言", desc: m.content, href: "messages.html", badge: "访客留言" });
    });
    items.sort(function (a, b) { return b.date - a.date; });
    items.slice(0, 12).forEach(function (it, idx) {
      const el = document.createElement("div");
      el.className = "tl-item reveal";
      el.style.transitionDelay = (idx % 4) * 0.05 + "s";
      el.innerHTML =
        '<span class="tl-dot"></span>' +
        '<div class="tl-meta"><span class="tl-date mono">' + T.fmtDate(it.date) + '</span><span class="tl-badge ' + it.type + '">' + it.badge + '</span></div>' +
        '<a class="tl-card" href="' + it.href + '"><div class="tl-title">' + (it.type === "moment" ? "“" + it.title + "”" : it.title) + '</div>' +
        '<div class="tl-desc">' + (it.type === "moment" ? it.desc : it.desc) + '</div></a>';
      wrap.appendChild(el);
    });
    initReveal();
  }

  /* ---------- Article list ---------- */
  function renderArticleList() {
    const grid = document.getElementById("article-grid");
    if (!grid) return;
    const d = T.load();
    const arts = d.articles.filter(function (a) { return a.status === "published"; }).sort(function (a, b) { return b.date - a.date; });
    if (!arts.length) {
      grid.innerHTML = '<div class="empty"><i>📄</i>暂无文章</div>';
      return;
    }
    arts.forEach(function (a, idx) {
      const cover = '<div class="article-cover">' + (a.cover ? '<img src="' + a.cover + '" alt="">' : '<div class="cover-fallback" style="background:' + "linear-gradient(135deg," + ["#5B8DEF", "#7C6CF0"][idx % 2] + ", " + ["#7C6CF0", "#5B8DEF"][idx % 2] + ')">' + (a.category || "T").charAt(0) + '</div>') + '<span class="article-cat">' + a.category + '</span></div>';
      const el = document.createElement("a");
      el.href = "article.html?id=" + a.id;
      el.className = "article-card reveal";
      el.innerHTML =
        cover +
        '<div class="article-body">' +
        '<h3 class="article-title">' + a.title + '</h3>' +
        '<p class="article-summary">' + a.summary + '</p>' +
        (a.tags && a.tags.length ? '<div class="article-tags">' + a.tags.map(function (t) { return '<span class="tag">#' + t + '</span>'; }).join("") + '</div>' : "") +
        '<div class="article-meta"><span>📅 ' + T.fmtDate(a.date) + '</span><span>⏱ ' + (a.readTime || T.readTimeOf(a.content)) + ' 分钟</span><span>👁 ' + (a.views || 0) + '</span></div>' +
        '</div>';
      grid.appendChild(el);
    });
    initReveal();
  }

  /* ---------- Article detail ---------- */
  function renderArticleDetail() {
    const wrap = document.getElementById("article-detail");
    if (!wrap) return;
    const id = new URLSearchParams(location.search).get("id");
    const a = T.getArticle(id);
    if (!a) {
      wrap.innerHTML = '<div class="empty"><i>🔍</i>文章不存在或已被删除<br><br><a class="btn btn-primary" href="articles.html">返回文章列表</a></div>';
      return;
    }
    // increment views
    a.views = (a.views || 0) + 1; T.save();

    const mdHtml = MD.parse(a.content);
    const toc = MD.extractToc(a.content);
    document.title = a.title + " · " + T.load().settings.siteTitle;

    const cover = a.cover ? '<img src="' + a.cover + '" alt="">' : '<div class="cover-fallback" style="background:linear-gradient(135deg,#5B8DEF,#7C6CF0)">' + (a.category || "T").charAt(0) + '</div>';

    wrap.innerHTML =
      '<div class="detail-cover">' + cover + '</div>' +
      '<h1 class="detail-title">' + a.title + '</h1>' +
      '<div class="detail-meta">' +
      '<span class="tag">' + a.category + '</span>' +
      '<span class="dot"></span><span>📅 ' + T.fmtDate(a.date) + '</span>' +
      '<span class="dot"></span><span>⏱ ' + (a.readTime || T.readTimeOf(a.content)) + ' 分钟阅读</span>' +
      '<span class="dot"></span><span>👁 ' + (a.views || 0) + ' 次浏览</span>' +
      '</div>' +
      '<article class="markdown-body" id="md-body">' + mdHtml + '</article>';

    // add ids to headings for TOC
    if (toc.length) {
      const hs = wrap.querySelectorAll("#md-body h2, #md-body h3, #md-body h4");
      let ti = 0;
      hs.forEach(function (h) {
        if (toc[ti] && h.tagName.toLowerCase() === "h" + toc[ti].level) {
          h.id = toc[ti].id; ti++;
        } else if (ti < toc.length) {
          // skip unmatched
          while (ti < toc.length && h.tagName.toLowerCase() !== "h" + toc[ti].level) ti++;
          if (ti < toc.length) { h.id = toc[ti].id; ti++; }
        }
      });
    }

    // TOC sidebar
    const tocEl = document.getElementById("toc-list");
    if (tocEl) {
      if (!toc.length) { tocEl.parentElement.style.display = "none"; }
      else {
        toc.forEach(function (t) {
          const aEl = document.createElement("a");
          aEl.className = "toc-link" + (t.level === 3 ? " lv3" : "") + (t.level === 4 ? " lv3" : "");
          aEl.href = "#" + t.id;
          aEl.textContent = t.title;
          aEl.dataset.target = t.id;
          tocEl.appendChild(aEl);
        });
      }
    }

    // related articles
    const related = document.getElementById("related-grid");
    if (related) {
      const d = T.load();
      const rel = d.articles.filter(function (x) { return x.id !== a.id && x.status === "published" && (x.category === a.category || (x.tags || []).some(function (t) { return (a.tags || []).includes(t); })); });
      const fill = d.articles.filter(function (x) { return x.id !== a.id && x.status === "published"; }).slice(0, 3);
      const list = rel.length ? rel.slice(0, 3) : fill;
      if (!list.length) related.innerHTML = '<div class="empty" style="padding:20px"><i>📭</i>暂无相关文章</div>';
      else list.forEach(function (r) {
        const el = document.createElement("a");
        el.href = "article.html?id=" + r.id;
        el.className = "article-card";
        el.innerHTML =
          '<div class="article-cover" style="height:120px">' + (r.cover ? '<img src="' + r.cover + '">' : '<div class="cover-fallback" style="font-size:26px;background:linear-gradient(135deg,#5B8DEF,#7C6CF0)">' + (r.category || "T").charAt(0) + '</div>') + '</div>' +
          '<div class="article-body" style="padding:14px 16px"><h4 class="article-title" style="font-size:14.5px">' + r.title + '</h4><div class="article-meta" style="margin-top:10px"><span>📅 ' + T.fmtDate(r.date) + '</span><span>⏱ ' + (r.readTime || T.readTimeOf(r.content)) + ' 分钟</span></div></div>';
        related.appendChild(el);
      });
    }

    initReadingProgress();
    initTocScroll();
  }

  /* ---------- Reading progress ---------- */
  function initReadingProgress() {
    const bar = document.getElementById("read-progress");
    if (!bar) return;
    function update() {
      const h = document.documentElement;
      const total = h.scrollHeight - h.clientHeight;
      const p = total > 0 ? (h.scrollTop / total) * 100 : 0;
      bar.style.width = p + "%";
    }
    window.addEventListener("scroll", update, { passive: true });
    update();
  }

  /* ---------- TOC scroll spy ---------- */
  function initTocScroll() {
    const links = document.querySelectorAll(".toc-link");
    if (!links.length) return;
    const headings = Array.from(links).map(function (l) { return document.getElementById(l.dataset.target); }).filter(Boolean);
    function spy() {
      let current = null;
      const pos = window.scrollY + 120;
      headings.forEach(function (h) { if (h.offsetTop <= pos) current = h.id; });
      links.forEach(function (l) {
        l.classList.toggle("active", l.dataset.target === current);
      });
    }
    window.addEventListener("scroll", spy, { passive: true });
    spy();
  }

  /* ---------- Moments page ---------- */
  function renderMoments() {
    const wrap = document.getElementById("moments-list");
    if (!wrap) return;
    const d = T.load();
    if (!d.moments.length) { wrap.innerHTML = '<div class="empty"><i>🕐</i>暂无动态</div>'; return; }
    d.moments.sort(function (a, b) { return b.date - a.date; }).forEach(function (m, idx) {
      const el = document.createElement("div");
      el.className = "moment-card reveal";
      el.dataset.id = m.id;
      const liked = m.likes.some(function (l) { return l.name === "我"; });
      const imgGrid = m.images.length === 1
        ? '<div class="moment-images one">' + m.images.map(function (im) { return '<img src="' + im + '" alt="">'; }).join("") + '</div>'
        : (m.images.length ? '<div class="moment-images">' + m.images.map(function (im) { return '<img src="' + im + '" alt="">'; }).join("") + '</div>' : "");
      el.innerHTML =
        '<div class="moment-head">' +
        '<img class="moment-avatar" src="' + T.svgAvatar("T", 0) + '" alt="">' +
        '<div class="info"><div class="moment-name">Tnine' + (m.private ? '<span class="moment-privacy">🔒 私密</span>' : "") + '</div><div class="moment-time">' + T.timeAgo(m.date) + ' · ' + T.fmtDate(m.date) + '</div></div>' +
        '</div>' +
        '<div class="moment-text">' + escapeHtml(m.text) + '</div>' +
        imgGrid +
        '<div class="moment-actions">' +
        '<button class="moment-action' + (liked ? " liked" : "") + '" data-like>' + (liked ? "❤️" : "🤍") + ' <span>' + m.likes.length + '</span></button>' +
        '<button class="moment-action" data-comment>💬 评论</button>' +
        '</div>' +
        '<div class="like-area' + (m.likes.length ? "" : " hidden") + '">' +
        (m.likes.length ? "❤️ " + m.likes.map(function (l) { return '<span class="like-user">' + l.name + '</span>'; }).join("，") : "") +
        '</div>' +
        '<div class="comment-area">' +
        '<div class="comments-inner"></div>' +
        '<button class="comment-toggle' + (m.comments.length > 2 ? "" : " hidden") + '" data-toggle>查看全部评论</button>' +
        '<div class="comment-form"><textarea placeholder="说点什么..." rows="1"></textarea><button class="btn btn-primary btn-sm comment-send">发送</button></div>' +
        '</div>';
      wrap.appendChild(el);

      // render comments (collapsed)
      const inner = el.querySelector(".comments-inner");
      const showAll = m.comments.length <= 2;
      m.comments.forEach(function (c, ci) {
        const item = document.createElement("div");
        item.className = "comment-item" + (showAll || ci >= m.comments.length - 2 ? "" : " hidden");
        item.innerHTML = '<span class="c-user">' + c.name + '</span>' + (c.replyTo ? ' <span class="c-reply">回复 ' + c.replyTo + '</span>：' : "：") + c.text +
          ' <span class="c-time" style="color:var(--text-3);font-size:11.5px;margin-left:6px">' + T.timeAgo(c.time) + '</span>';
        inner.appendChild(item);
      });

      const toggle = el.querySelector("[data-toggle]");
      if (toggle) {
        toggle.addEventListener("click", function () {
          const hiddenItems = inner.querySelectorAll(".comment-item.hidden");
          if (hiddenItems.length) {
            hiddenItems.forEach(function (h) { h.classList.remove("hidden"); });
            toggle.textContent = "收起评论";
          } else {
            inner.querySelectorAll(".comment-item").forEach(function (it, i) { if (i < m.comments.length - 2) it.classList.add("hidden"); });
            toggle.textContent = "查看全部评论";
          }
        });
      }

      // like
      el.querySelector("[data-like]").addEventListener("click", function () {
        const isLiked = m.likes.some(function (l) { return l.name === "我"; });
        if (isLiked) m.likes = m.likes.filter(function (l) { return l.name !== "我"; });
        else m.likes.push({ name: "我" });
        T.save();
        renderMoments(); toast(isLiked ? "已取消点赞" : "点赞成功");
      });

      // comment send
      const ta = el.querySelector("textarea");
      el.querySelector(".comment-send").addEventListener("click", function () {
        const v = ta.value.trim();
        if (!v) return toast("评论不能为空", "error");
        m.comments.push({ name: "我", text: v, time: Date.now(), replyTo: null });
        ta.value = ""; T.save();
        renderMoments(); toast("评论成功");
      });
      ta.addEventListener("input", function () { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 120) + "px"; });
    });
    initReveal();
    initLightbox();
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  /* ---------- Lightbox ---------- */
  function initLightbox() {
    const lb = document.getElementById("lightbox");
    if (!lb) return;
    document.querySelectorAll(".moment-images img").forEach(function (img) {
      img.addEventListener("click", function () {
        lb.innerHTML = '<img src="' + img.src + '">';
        lb.classList.add("open");
      });
    });
    lb.addEventListener("click", function () { lb.classList.remove("open"); });
  }

  /* ---------- Messages page ---------- */
  const AVATARS = ["🌱", "🍀", "🦊", "🐱", "🐼", "🦉", "🌸", "⭐"];
  const RANDOM_NAMES = ["清风徐来", "夜航星", "追光的猫", "山间明月", "煮雪烹茶", "晚风", "一只梨", "海盐芝士", "拾光者", "小满", "墨白", "南巷清风"];
  function currentIdentity() {
    try {
      let id = localStorage.getItem("tnine_visitor");
      if (!id) {
        id = {
          nickname: T.randPick(RANDOM_NAMES),
          avatar: T.svgAvatar(T.randPick(RANDOM_NAMES), Math.floor(Math.random() * 8))
        };
        localStorage.setItem("tnine_visitor", JSON.stringify(id));
      } else { id = JSON.parse(id); }
      return id;
    } catch (e) { return { nickname: "匿名访客", avatar: T.svgAvatar("匿", 3) }; }
  }

  function renderMessages() {
    const wrap = document.getElementById("message-list");
    if (!wrap) return;
    const d = T.load();
    const list = d.messages.filter(function (m) { return !m.isPrivate; }).sort(function (a, b) { return b.date - a.date; });
    if (!list.length) { wrap.innerHTML = '<div class="empty"><i>💬</i>还没有留言，来抢沙发吧</div>'; return; }
    list.forEach(function (m) {
      const el = document.createElement("div");
      el.className = "message-item reveal" + (m.important ? " important" : "");
      el.innerHTML =
        '<div class="message-head">' +
        '<img class="message-avatar" src="' + m.avatar + '" alt="">' +
        '<span class="message-name">' + m.nickname + '</span>' +
        (m.important ? '<span class="message-badge important-b">⭐ 重要</span>' : "") +
        '<span class="message-time">' + T.timeAgo(m.date) + '</span>' +
        '</div>' +
        '<div class="message-content">' + escapeHtml(m.content) + '</div>' +
        (m.replies && m.replies.length ? '<div class="message-reply"><span class="reply-name">' + m.replies[0].name + '</span>：' + escapeHtml(m.replies[0].content) + '</div>' : "");
      wrap.appendChild(el);
    });
    initReveal();
  }

  function initMessageForm() {
    const form = document.getElementById("message-form");
    if (!form) return;
    const id = currentIdentity();
    const nickInput = document.getElementById("msg-nick");
    const avatarPicker = document.getElementById("avatar-picker");
    if (nickInput) nickInput.value = id.nickname;
    if (avatarPicker) {
      const set = [id.avatar];
      AVATARS.slice(0, 7).forEach(function (e) { set.push(T.svgAvatar(e, Math.floor(Math.random() * 8))); });
      set.forEach(function (av, i) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "avatar-option" + (i === 0 ? " selected" : "");
        btn.innerHTML = '<img src="' + av + '" style="width:100%;height:100%;border-radius:12px">';
        btn.addEventListener("click", function () {
          avatarPicker.querySelectorAll(".avatar-option").forEach(function (b) { b.classList.remove("selected"); });
          btn.classList.add("selected");
          selectedAvatar = av;
        });
        avatarPicker.appendChild(btn);
      });
    }
    let selectedAvatar = id.avatar;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      const d = T.load();
      const nick = (nickInput.value || "").trim() || id.nickname;
      const content = document.getElementById("msg-content").value.trim();
      const privacy = document.querySelector('input[name="privacy"]:checked').value;
      if (!content) return toast("留言内容不能为空", "error");
      d.messages.unshift({
        id: T.uid("msg"), nickname: nick, avatar: selectedAvatar,
        content: content, date: Date.now(), isPrivate: privacy === "private",
        important: false, replies: []
      });
      if (privacy === "private") {
        d.notifications.unshift({ id: T.uid("n"), type: "message", user: nick, avatar: selectedAvatar, action: "给你留了一条私密留言", target: content.slice(0, 30), targetUrl: "admin.html", date: Date.now(), read: false });
      } else {
        d.notifications.unshift({ id: T.uid("n"), type: "message", user: nick, avatar: selectedAvatar, action: "给你留了一条言", target: content.slice(0, 30), targetUrl: "admin.html", date: Date.now(), read: false });
      }
      T.save();
      try {
        const stored = JSON.parse(localStorage.getItem("tnine_visitor") || "null");
        localStorage.setItem("tnine_visitor", JSON.stringify({ nickname: nick, avatar: selectedAvatar }));
      } catch (err) {}
      form.reset();
      nickInput.value = nick;
      toast(privacy === "private" ? "私密留言已发送，仅站长可见" : "留言成功，感谢你的来访");
      renderMessages();
    });
  }

  /* ---------- Init ---------- */
  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    initNav();
    renderHomeTimeline();
    renderArticleList();
    renderArticleDetail();
    renderMoments();
    renderMessages();
    initMessageForm();
  });
})();
