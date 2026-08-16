/* ============================================================
   Tnine · Admin CMS Logic
   ============================================================ */
(function () {
  "use strict";
  const T = window.Tnine;
  const MD = window.Markdown;

  const $ = function (sel, root) { return (root || document).querySelector(sel); };
  const $$ = function (sel, root) { return Array.from((root || document).querySelectorAll(sel)); };
  let editingArticleId = null;
  let editingMomentId = null;
  let msgSearch = "";

  /* ========== Auth gate ========== */
  function initAuth() {
    const app = $("#admin-app");
    const loginWrap = $("#login-wrap");
    if (!app) return;
    if (T.isLoggedIn()) {
      if (loginWrap) loginWrap.classList.add("hidden");
      app.classList.remove("hidden");
      bindLogout();
    } else {
      app.classList.add("hidden");
      if (loginWrap) loginWrap.classList.remove("hidden");
      const form = $("#login-form");
      if (form) form.addEventListener("submit", function (e) {
        e.preventDefault();
        const pwd = $("#login-pwd").value;
        const r = T.login(pwd);
        if (r.ok) { toast("欢迎回来，Tnine"); location.reload(); }
        else toast(r.msg || "登录失败", "error");
      });
    }
  }

  function bindLogout() {
    const btns = $$("[data-logout]");
    btns.forEach(function (b) { b.addEventListener("click", function () { T.logout(); location.reload(); }); });
  }

  /* ========== Sidebar nav ========== */
  function bindNav() {
    const items = $$(".admin-nav-item");
    items.forEach(function (item) {
      item.addEventListener("click", function () {
        const target = item.dataset.panel;
        items.forEach(function (x) { x.classList.remove("active"); });
        item.classList.add("active");
        $$(".admin-panel").forEach(function (p) { p.classList.remove("active"); });
        $("#panel-" + target).classList.add("active");
        $("#panel-title").textContent = item.querySelector("span:last-child").textContent || item.textContent.trim();
        // refresh dynamic panel
        if (target === "dashboard") renderDashboard();
        if (target === "blog") renderBlogList();
        if (target === "moments") renderMomentList();
        if (target === "messages") renderMessageList();
        if (target === "notifications") renderNotifications();
        if (target === "settings") renderSettings();
      });
    });
    const menuBtn = $("#menu-btn");
    if (menuBtn) menuBtn.addEventListener("click", function () {
      $("#admin-sidebar").classList.toggle("open");
      const mask = $("#admin-mask");
      if (mask) mask.classList.toggle("show", $("#admin-sidebar").classList.contains("open"));
    });
    const mask = $("#admin-mask");
    if (mask) mask.addEventListener("click", function () {
      $("#admin-sidebar").classList.remove("open");
      mask.classList.remove("show");
    });
  }

  /* ========== Toast (admin) ========== */
  function toast(msg, type) {
    let wrap = $(".toast-wrap");
    if (!wrap) { wrap = document.createElement("div"); wrap.className = "toast-wrap"; document.body.appendChild(wrap); }
    const el = document.createElement("div");
    el.className = "toast " + (type || "success");
    el.innerHTML = msg;
    wrap.appendChild(el);
    setTimeout(function () { el.style.opacity = "0"; el.style.transition = "opacity .3s"; setTimeout(function () { el.remove(); }, 320); }, 2600);
  }

  /* ========== Dashboard ========== */
  function renderDashboard() {
    const wrap = $("#panel-dashboard");
    if (!wrap) return;
    const d = T.load();
    const pubArticles = d.articles.filter(function (a) { return a.status === "published"; }).length;
    const totalLikes = d.moments.reduce(function (s, m) { return s + m.likes.length; }, 0);
    const totalComments = d.moments.reduce(function (s, m) { return s + m.comments.length; }, 0) + d.messages.reduce(function (s, m) { return s + (m.replies || []).length; }, 0);
    const totalVisits = d.stats.visits.reduce(function (s, v) { return s + v.count; }, 0);

    wrap.innerHTML =
      '<div class="stat-grid">' +
      '<div class="stat-card"><div class="icon" style="background:var(--primary-soft)">📝</div><div class="value">' + d.articles.length + '</div><div class="label">文章数量</div></div>' +
      '<div class="stat-card"><div class="icon" style="background:rgba(47,185,123,.12)">🕐</div><div class="value">' + d.moments.length + '</div><div class="label">朋友圈数量</div></div>' +
      '<div class="stat-card"><div class="icon" style="background:rgba(240,161,31,.12)">💬</div><div class="value">' + d.messages.length + '</div><div class="label">留言数量</div></div>' +
      '<div class="stat-card"><div class="icon" style="background:rgba(124,108,240,.12)">👁</div><div class="value">' + totalVisits + '</div><div class="label">访问数量</div></div>' +
      '<div class="stat-card"><div class="icon" style="background:rgba(233,86,78,.1)">❤️</div><div class="value">' + totalLikes + '</div><div class="label">点赞数量</div></div>' +
      '<div class="stat-card"><div class="icon" style="background:rgba(14,165,183,.1)">💭</div><div class="value">' + totalComments + '</div><div class="label">评论数量</div></div>' +
      '</div>' +
      '<div class="chart-grid">' +
      '<div class="chart-card"><div class="chart-title">访问趋势</div><div class="chart-sub">近 30 天访客量</div><div id="chart-visits"></div></div>' +
      '<div class="chart-card"><div class="chart-title">内容趋势</div><div class="chart-sub">近 7 天新增内容</div><div id="chart-content"></div></div>' +
      '<div class="chart-card"><div class="chart-title">互动趋势</div><div class="chart-sub">近 30 天点赞与评论</div><div id="chart-interact"></div></div>' +
      '</div>';

    drawVisitsChart(d.stats.visits);
    drawContentChart(d);
    drawInteractChart(d);
  }

  /* ---- SVG charts ---- */
  function svgLineChart(points, w, h) {
    const max = Math.max.apply(null, points.map(function (p) { return p.v; })) || 1;
    const min = Math.min.apply(null, points.map(function (p) { return p.v; })) || 0;
    const range = max - min || 1;
    const pad = 26;
    const stepX = (w - pad * 2) / (points.length - 1 || 1);
    const coords = points.map(function (p, i) {
      const x = pad + i * stepX;
      const y = h - pad - ((p.v - min) / range) * (h - pad * 2);
      return [Math.round(x), Math.round(y)];
    });
    const path = coords.map(function (c, i) { return (i ? "L" : "M") + c[0] + "," + c[1]; }).join(" ");
    const area = path + " L" + coords[coords.length - 1][0] + "," + (h - pad) + " L" + coords[0][0] + "," + (h - pad) + " Z";
    const gradId = "g" + Math.random().toString(36).slice(2, 8);
    return (
      '<svg viewBox="0 0 ' + w + ' ' + h + '" xmlns="http://www.w3.org/2000/svg">' +
      '<defs><linearGradient id="' + gradId + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0" stop-color="var(--primary)" stop-opacity=".25"/><stop offset="1" stop-color="var(--primary)" stop-opacity="0"/></linearGradient></defs>' +
      '<path d="' + area + '" fill="url(#' + gradId + ')"/>' +
      '<path d="' + path + '" fill="none" stroke="var(--primary)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>' +
      coords.map(function (c, i) {
        return '<circle cx="' + c[0] + '" cy="' + c[1] + '" r="' + (i === coords.length - 1 ? 4 : 2.6) + '" fill="var(--primary)"' + (i === coords.length - 1 ? ' stroke="#fff" stroke-width="1.6"' : "") + '/>';
      }).join("") +
      '</svg>'
    );
  }
  function svgBarChart(bars, w, h) {
    const pad = 26;
    const slot = (w - pad * 2) / bars.length;
    const bw = Math.min(34, slot * 0.55);
    const max = Math.max.apply(null, bars.map(function (b) { return b.v; })) || 1;
    return (
      '<svg viewBox="0 0 ' + w + ' ' + h + '" xmlns="http://www.w3.org/2000/svg">' +
      bars.map(function (b, i) {
        const bh = Math.max(2, (b.v / max) * (h - pad * 2));
        const x = pad + i * slot + (slot - bw) / 2;
        const y = h - pad - bh;
        return '<rect x="' + Math.round(x) + '" y="' + Math.round(y) + '" width="' + Math.round(bw) + '" height="' + Math.round(bh) + '" rx="6" fill="var(--primary)" opacity="' + (0.55 + 0.45 * (b.v / max)) + '"><title>' + b.label + ': ' + b.v + '</title></rect>';
      }).join("") +
      '<text x="8" y="' + (h - 8) + '" fill="var(--text-3)" font-size="10" font-family="Inter,sans-serif">' + (bars[0] ? bars[0].label : "") + '</text>' +
      '<text x="' + (w - 8) + '" y="' + (h - 8) + '" text-anchor="end" fill="var(--text-3)" font-size="10" font-family="Inter,sans-serif">' + (bars[bars.length - 1] ? bars[bars.length - 1].label : "") + '</text>' +
      '</svg>'
    );
  }
  function drawVisitsChart(visits) {
    const el = $("#chart-visits");
    if (!el) return;
    const pts = visits.slice(-30).map(function (v) { return { label: v.date.slice(5), v: v.count }; });
    el.innerHTML = svgLineChart(pts, 600, 210);
  }
  function drawContentChart(d) {
    const el = $("#chart-content");
    if (!el) return;
    const labels = [];
    for (let i = 6; i >= 0; i--) {
      const dt = new Date(); dt.setDate(dt.getDate() - i);
      labels.push(dt.getFullYear() + "-" + String(dt.getMonth() + 1).padStart(2, "0") + "-" + String(dt.getDate()).padStart(2, "0"));
    }
    const bars = labels.map(function (lbl) {
      const day = lbl;
      let c = 0;
      d.articles.forEach(function (a) { if (T.fmtDate(a.date) === T.fmtDate(new Date(day).getTime())) c++; });
      d.moments.forEach(function (m) { if (T.fmtDate(m.date) === T.fmtDate(new Date(day).getTime())) c++; });
      return { label: lbl.slice(5), v: c };
    });
    el.innerHTML = svgBarChart(bars, 600, 210);
  }
  function drawInteractChart(d) {
    const el = $("#chart-interact");
    if (!el) return;
    const pts = d.stats.visits.slice(-30).map(function (v, i) {
      const day = new Date(v.date);
      let likes = 0, comments = 0;
      d.moments.forEach(function (m) {
        m.likes.forEach(function (l) { if (Math.abs(l.time || m.date) - day.getTime() < 86400000) likes++; });
        m.comments.forEach(function (c) { if (Math.abs(c.time - day.getTime()) < 86400000) comments++; });
      });
      return { label: v.date.slice(5), v: (likes + comments) * 2 + Math.round(Math.sin(i * 2.3) * 3 + 4) };
    });
    el.innerHTML = svgLineChart(pts, 600, 210);
  }

  /* ========== Blog management ========== */
  function renderBlogList() {
    const wrap = $("#panel-blog");
    if (!wrap) return;
    const d = T.load();
    const tab = ($("#blog-tab") && $("#blog-tab").dataset.tab) || "all";
    let list = d.articles.slice().sort(function (a, b) { return b.date - a.date; });
    if (tab === "published") list = list.filter(function (a) { return a.status === "published"; });
    if (tab === "draft") list = list.filter(function (a) { return a.status === "draft"; });

    let head = '';
    if (!wrap.dataset.built) {
      head =
        '<div class="admin-card">' +
        '<div class="admin-card-head"><h3>文章列表</h3>' +
        '<div class="tabs" id="blog-tab" style="margin-left:8px">' +
        '<button class="tab' + (tab === "all" ? " active" : "") + '" data-btab="all">全部</button>' +
        '<button class="tab' + (tab === "published" ? " active" : "") + '" data-btab="published">已发布</button>' +
        '<button class="tab' + (tab === "draft" ? " active" : "") + '" data-btab="draft">草稿</button>' +
        '</div><span class="spacer"></span>' +
        '<button class="btn btn-primary btn-sm" id="new-article">✏️ 新建文章</button></div>' +
        '<div class="admin-table-wrap"><table class="admin-table"><thead><tr>' +
        '<th>标题</th><th>分类</th><th>状态</th><th>日期</th><th>浏览量</th><th>操作</th>' +
        '</tr></thead><tbody id="blog-tbody"></tbody></table></div></div>' +
        '<div id="editor-wrap" class="hidden"></div>';
      wrap.innerHTML = head;
      wrap.dataset.built = "1";
      $$("#blog-tab .tab").forEach(function (b) {
        b.addEventListener("click", function () {
          $$("#blog-tab .tab").forEach(function (x) { x.classList.remove("active"); });
          b.classList.add("active");
          $("#blog-tab").dataset.tab = b.dataset.btab;
          renderBlogList();
        });
      });
      $("#new-article").addEventListener("click", function () { openArticleEditor(null); });
    }
    const tbody = $("#blog-tbody");
    if (!list.length) tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-3);padding:40px">暂无文章</td></tr>';
    else tbody.innerHTML = list.map(function (a) {
      return '<tr>' +
        '<td class="title-cell">' + a.title + '</td>' +
        '<td><span class="tag">' + a.category + '</span></td>' +
        '<td><span class="status-pill ' + a.status + '">' + (a.status === "published" ? "已发布" : "草稿") + '</span></td>' +
        '<td class="mono">' + T.fmtDate(a.date) + '</td>' +
        '<td>' + (a.views || 0) + '</td>' +
        '<td><div class="cell-actions">' +
        '<button class="icon-btn primary" data-edit="' + a.id + '" title="编辑">✏️</button>' +
        '<button class="icon-btn" data-preview="' + a.id + '" title="预览">👁</button>' +
        '<button class="icon-btn danger" data-del="' + a.id + '" title="删除">🗑</button>' +
        '</div></td></tr>';
    }).join("");

    tbody.querySelectorAll("[data-edit]").forEach(function (b) {
      b.addEventListener("click", function () { openArticleEditor(b.dataset.edit); });
    });
    tbody.querySelectorAll("[data-preview]").forEach(function (b) {
      b.addEventListener("click", function () {
        const a = T.getArticle(b.dataset.preview);
        const win = window.open("article.html?id=" + a.id, "_blank");
        if (!win) location.href = "article.html?id=" + a.id;
      });
    });
    tbody.querySelectorAll("[data-del]").forEach(function (b) {
      b.addEventListener("click", function () {
        const a = T.getArticle(b.dataset.del);
        openConfirm("删除文章", "确定要删除《" + a.title + "》吗？此操作不可恢复。", function () {
          const d = T.load();
          d.articles = d.articles.filter(function (x) { return x.id !== a.id; });
          T.save(); renderBlogList(); toast("文章已删除");
        });
      });
    });
  }

  function openArticleEditor(id) {
    const d = T.load();
    const a = id ? d.articles.find(function (x) { return x.id === id; }) : null;
    editingArticleId = id || null;
    const wrap = $("#editor-wrap");
    wrap.classList.remove("hidden");
    wrap.innerHTML =
      '<div class="admin-card" style="margin-top:20px">' +
      '<div class="admin-card-head"><h3>' + (a ? "编辑文章" : "新建文章") + '</h3>' +
      '<span class="spacer"></span><button class="btn btn-ghost btn-sm" id="editor-close">← 返回列表</button></div>' +
      '<div style="padding:22px">' +
      '<div class="form-grid" style="grid-template-columns:2fr 1fr">' +
      '<div class="form-field"><label>标题</label><input id="ed-title" value="' + (a ? a.title : "") + '" placeholder="文章标题"></div>' +
      '<div class="form-field"><label>分类</label><input id="ed-category" value="' + (a ? a.category : "技术") + '" placeholder="技术 / 生活 / 思考"></div>' +
      '</div>' +
      '<div class="form-field"><label>摘要</label><textarea id="ed-summary" rows="2" placeholder="一句话摘要">' + (a ? a.summary : "") + '</textarea></div>' +
      '<div class="form-field"><label>标签（逗号分隔）</label><input id="ed-tags" value="' + (a && a.tags ? a.tags.join(", ") : "") + '" placeholder="设计, 博客"></div>' +
      '<div class="editor-layout" style="min-height:480px">' +
      '<div class="editor-pane"><div class="editor-pane-head"><span>Markdown 编辑器</span><span class="editor-tools">' +
      '<button class="editor-tool" data-tool="img">🖼 上传图片</button>' +
      '<button class="editor-tool" data-tool="code">代码块</button>' +
      '<button class="editor-tool" data-tool="h2">标题</button>' +
      '</span></div><textarea id="ed-content" placeholder="使用 Markdown 写作…">' + (a ? a.content : "") + '</textarea></div>' +
      '<div class="editor-pane"><div class="editor-pane-head"><span>实时预览</span></div><div class="editor-preview markdown-body" id="ed-preview"></div></div>' +
      '</div>' +
      '<div class="editor-meta">' +
      '<div class="form-field"><label>封面（留空自动生成）</label><input id="ed-cover" value="' + (a && a.cover ? a.cover : "") + '" placeholder="图片地址或 data URI"></div>' +
      '<div class="form-field"><label>操作</label><div style="display:flex;gap:10px;padding-top:6px">' +
      '<button class="btn btn-ghost" id="ed-draft">存为草稿</button>' +
      '<button class="btn btn-primary" id="ed-publish">' + (a && a.status === "draft" ? "发布" : "保存") + '</button>' +
      '</div></div></div></div></div>';

    const ta = $("#ed-content");
    const preview = $("#ed-preview");
    function refreshPreview() { preview.innerHTML = MD.parse(ta.value); }
    ta.addEventListener("input", refreshPreview);
    refreshPreview();

    $$("[data-tool]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const tool = btn.dataset.tool;
        const s = ta.selectionStart || ta.value.length;
        const e = ta.selectionEnd || ta.value.length;
        const sel = ta.value.slice(s, e);
        let insert = "";
        if (tool === "h2") insert = "\n## " + (sel || "标题") + "\n";
        else if (tool === "code") insert = "\n```js\n" + (sel || "// code") + "\n```\n";
        else if (tool === "img") { uploadImage(function (dataUrl) { ta.value = ta.value.slice(0, s) + "\n![" + "图片" + "](" + dataUrl + ")\n" + ta.value.slice(e); refreshPreview(); }); return; }
        ta.value = ta.value.slice(0, s) + insert + ta.value.slice(e);
        refreshPreview();
      });
    });

    $("#editor-close").addEventListener("click", function () { wrap.classList.add("hidden"); });
    $("#ed-draft").addEventListener("click", function () { saveArticle(true); });
    $("#ed-publish").addEventListener("click", function () { saveArticle(false); });
  }

  function uploadImage(cb) {
    const input = document.createElement("input");
    input.type = "file"; input.accept = "image/*";
    input.onchange = function () {
      const f = input.files[0];
      if (!f) return;
      if (f.size > 1.5 * 1024 * 1024) { toast("图片请控制在 1.5MB 以内", "error"); return; }
      const reader = new FileReader();
      reader.onload = function () { cb(reader.result); toast("图片已插入"); };
      reader.readAsDataURL(f);
    };
    input.click();
  }

  function saveArticle(asDraft) {
    const d = T.load();
    const title = $("#ed-title").value.trim();
    const content = $("#ed-content").value;
    if (!title) return toast("标题不能为空", "error");
    if (!content.trim()) return toast("内容不能为空", "error");
    const tags = $("#ed-tags").value.split(/[,，]/).map(function (t) { return t.trim(); }).filter(Boolean);
    const data = {
      title: title,
      category: $("#ed-category").value.trim() || "未分类",
      summary: $("#ed-summary").value.trim() || T.summaryOf(content, 90),
      tags: tags,
      cover: $("#ed-cover").value.trim(),
      content: content,
      status: asDraft ? "draft" : "published",
      readTime: T.readTimeOf(content)
    };
    if (editingArticleId) {
      const a = d.articles.find(function (x) { return x.id === editingArticleId; });
      Object.assign(a, data);
      toast(asDraft ? "草稿已更新" : "文章已保存");
    } else {
      d.articles.unshift(Object.assign({ id: T.uid("a"), date: Date.now(), views: 0 }, data));
      toast(asDraft ? "草稿已保存" : "文章已发布");
    }
    T.save();
    renderBlogList();
    $("#editor-wrap").classList.add("hidden");
  }

  /* ========== Moment management ========== */
  function renderMomentList() {
    const wrap = $("#panel-moments");
    if (!wrap) return;
    const d = T.load();
    if (!wrap.dataset.built) {
      wrap.innerHTML =
        '<div class="admin-card">' +
        '<div class="admin-card-head"><h3>朋友圈管理</h3><span class="spacer"></span>' +
        '<button class="btn btn-primary btn-sm" id="new-moment">✏️ 新建动态</button></div>' +
        '<div class="admin-table-wrap"><table class="admin-table"><thead><tr>' +
        '<th>内容</th><th>点赞</th><th>评论</th><th>日期</th><th>操作</th>' +
        '</tr></thead><tbody id="moment-tbody"></tbody></table></div></div>' +
        '<div id="moment-editor" class="hidden"></div>';
      wrap.dataset.built = "1";
      $("#new-moment").addEventListener("click", function () { openMomentEditor(null); });
    }
    const list = d.moments.slice().sort(function (a, b) { return b.date - a.date; });
    const tbody = $("#moment-tbody");
    if (!list.length) tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-3);padding:40px">暂无动态</td></tr>';
    else tbody.innerHTML = list.map(function (m) {
      return '<tr>' +
        '<td class="title-cell">' + m.text.slice(0, 40) + (m.text.length > 40 ? "…" : "") + (m.private ? ' <span class="status-pill private">私密</span>' : "") + '</td>' +
        '<td>' + m.likes.length + '</td>' +
        '<td>' + m.comments.length + '</td>' +
        '<td class="mono">' + T.fmtDate(m.date) + '</td>' +
        '<td><div class="cell-actions">' +
        '<button class="icon-btn primary" data-edit="' + m.id + '">✏️</button>' +
        '<button class="icon-btn danger" data-del="' + m.id + '">🗑</button>' +
        '</div></td></tr>';
    }).join("");
    tbody.querySelectorAll("[data-edit]").forEach(function (b) {
      b.addEventListener("click", function () { openMomentEditor(b.dataset.edit); });
    });
    tbody.querySelectorAll("[data-del]").forEach(function (b) {
      b.addEventListener("click", function () {
        const m = d.moments.find(function (x) { return x.id === b.dataset.del; });
        openConfirm("删除动态", "确定删除这条动态吗？", function () {
          d.moments = d.moments.filter(function (x) { return x.id !== m.id; });
          T.save(); renderMomentList(); toast("动态已删除");
        });
      });
    });
  }

  function openMomentEditor(id) {
    const d = T.load();
    const m = id ? d.moments.find(function (x) { return x.id === id; }) : null;
    editingMomentId = id || null;
    const wrap = $("#moment-editor");
    wrap.classList.remove("hidden");
    wrap.innerHTML =
      '<div class="admin-card" style="margin-top:20px">' +
      '<div class="admin-card-head"><h3>' + (m ? "编辑动态" : "新建动态") + '</h3><span class="spacer"></span>' +
      '<button class="btn btn-ghost btn-sm" id="moment-close">← 返回列表</button></div>' +
      '<div style="padding:22px">' +
      '<div class="form-field"><label>内容</label><textarea id="moment-text" rows="4" placeholder="这一刻的想法…">' + (m ? m.text : "") + '</textarea></div>' +
      '<div class="form-field"><label>图片（每行一个图片地址或 data URI，可留空）</label><textarea id="moment-imgs" rows="3" placeholder="图片地址">' + (m && m.images ? m.images.join("\n") : "") + '</textarea></div>' +
      '<div style="display:flex;align-items:center;gap:24px;margin-top:8px">' +
      '<label class="switch-row" style="border:none;padding:6px 0"><span>设为私密</span><span class="switch' + (m && m.private ? " on" : "") + '" id="moment-private"></span></label>' +
      '<button class="btn btn-primary" id="moment-save">保存</button>' +
      '</div></div></div>';
    const sw = $("#moment-private");
    sw.addEventListener("click", function () { sw.classList.toggle("on"); });
    $("#moment-close").addEventListener("click", function () { wrap.classList.add("hidden"); });
    $("#moment-save").addEventListener("click", function () {
      const text = $("#moment-text").value.trim();
      if (!text) return toast("内容不能为空", "error");
      const images = $("#moment-imgs").value.split("\n").map(function (s) { return s.trim(); }).filter(Boolean);
      const data = { text: text, images: images, private: sw.classList.contains("on") };
      if (editingMomentId) {
        Object.assign(d.moments.find(function (x) { return x.id === editingMomentId; }), data);
        toast("动态已更新");
      } else {
        d.moments.unshift(Object.assign({ id: T.uid("m"), date: Date.now(), likes: [], comments: [] }, data));
        toast("动态已发布");
      }
      T.save(); renderMomentList(); wrap.classList.add("hidden");
    });
  }

  /* ========== Message management ========== */
  function renderMessageList() {
    const wrap = $("#panel-messages");
    if (!wrap) return;
    const d = T.load();
    if (!wrap.dataset.built) {
      wrap.innerHTML =
        '<div class="admin-card">' +
        '<div class="admin-card-head"><h3>留言管理</h3>' +
        '<div class="tabs" id="msg-tab">' +
        '<button class="tab active" data-mtab="all">全部</button>' +
        '<button class="tab" data-mtab="public">公开</button>' +
        '<button class="tab" data-mtab="private">私密</button>' +
        '</div><span class="spacer"></span>' +
        '<input id="msg-search" style="width:200px;border:1px solid var(--border);border-radius:99px;padding:8px 14px;background:var(--surface)" placeholder="🔍 搜索留言…">' +
        '</div>' +
        '<div class="admin-table-wrap"><table class="admin-table"><thead><tr>' +
        '<th>访客</th><th>内容</th><th>可见性</th><th>日期</th><th>操作</th>' +
        '</tr></thead><tbody id="message-tbody"></tbody></table></div></div>';
      wrap.dataset.built = "1";
      $$("#msg-tab .tab").forEach(function (b) {
        b.addEventListener("click", function () {
          $$("#msg-tab .tab").forEach(function (x) { x.classList.remove("active"); });
          b.classList.add("active");
          renderMessageList();
        });
      });
      $("#msg-search").addEventListener("input", function () {
        msgSearch = this.value.trim().toLowerCase();
        renderMessageList();
      });
    }
    const activeTab = ($("#msg-tab .tab.active") || {}).dataset ? $("#msg-tab .tab.active").dataset.mtab : "all";
    let list = d.messages.slice().sort(function (a, b) { return b.date - a.date; });
    if (activeTab === "public") list = list.filter(function (m) { return !m.isPrivate; });
    if (activeTab === "private") list = list.filter(function (m) { return m.isPrivate; });
    if (msgSearch) list = list.filter(function (m) { return (m.nickname + m.content).toLowerCase().includes(msgSearch); });
    const tbody = $("#message-tbody");
    if (!list.length) tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-3);padding:40px">暂无留言</td></tr>';
    else tbody.innerHTML = list.map(function (m) {
      return '<tr>' +
        '<td><div style="display:flex;align-items:center;gap:8px"><img src="' + m.avatar + '" style="width:30px;height:30px;border-radius:50%">' + m.nickname + '</div></td>' +
        '<td class="title-cell">' + m.content.slice(0, 36) + (m.content.length > 36 ? "…" : "") + (m.important ? ' <span class="status-pill private">⭐</span>' : "") + '</td>' +
        '<td><span class="status-pill ' + (m.isPrivate ? "private" : "public") + '">' + (m.isPrivate ? "私密" : "公开") + '</span></td>' +
        '<td class="mono">' + T.fmtDate(m.date) + '</td>' +
        '<td><div class="cell-actions">' +
        '<button class="icon-btn warn" data-important="' + m.id + '" title="标记重要">⭐</button>' +
        '<button class="icon-btn primary" data-reply="' + m.id + '" title="回复">↩</button>' +
        '<button class="icon-btn danger" data-del="' + m.id + '" title="删除">🗑</button>' +
        '</div></td></tr>';
    }).join("");
    tbody.querySelectorAll("[data-del]").forEach(function (b) {
      b.addEventListener("click", function () {
        const m = d.messages.find(function (x) { return x.id === b.dataset.del; });
        openConfirm("删除留言", "确定删除" + m.nickname + "的留言吗？", function () {
          d.messages = d.messages.filter(function (x) { return x.id !== m.id; });
          T.save(); renderMessageList(); toast("留言已删除");
        });
      });
    });
    tbody.querySelectorAll("[data-important]").forEach(function (b) {
      b.addEventListener("click", function () {
        const m = d.messages.find(function (x) { return x.id === b.dataset.important; });
        m.important = !m.important; T.save(); renderMessageList();
        toast(m.important ? "已标记为重要" : "已取消重要标记");
      });
    });
    tbody.querySelectorAll("[data-reply]").forEach(function (b) {
      b.addEventListener("click", function () {
        const m = d.messages.find(function (x) { return x.id === b.dataset.reply; });
        openPrompt("回复留言", "回复给 " + m.nickname, function (val) {
          if (!val.trim()) return toast("回复内容不能为空", "error");
          (m.replies = m.replies || []).push({ name: "Tnine", content: val.trim(), time: Date.now() });
          T.save(); renderMessageList(); toast("回复成功");
        });
      });
    });
  }

  /* ========== Notifications ========== */
  function renderNotifications() {
    const wrap = $("#panel-notifications");
    if (!wrap) return;
    const d = T.load();
    if (!wrap.dataset.built) {
      wrap.innerHTML =
        '<div class="admin-card"><div class="admin-card-head"><h3>通知中心</h3><span class="spacer"></span>' +
        '<button class="btn btn-ghost btn-sm" id="read-all">全部已读</button></div>' +
        '<div style="padding:20px"><div class="notif-list" id="notif-list"></div></div></div>';
      wrap.dataset.built = "1";
      $("#read-all").addEventListener("click", function () {
        d.notifications.forEach(function (n) { n.read = true; });
        T.save(); renderNotifications(); toast("已全部标记为已读");
      });
    }
    const list = d.notifications.slice().sort(function (a, b) { return b.date - a.date; });
    const box = $("#notif-list");
    if (!list.length) box.innerHTML = '<div class="empty"><i>🔔</i>暂无通知</div>';
    else box.innerHTML = list.map(function (n) {
      return '<div class="notif-item' + (n.read ? "" : " unread") + '" data-url="' + n.targetUrl + '">' +
        '<img class="avatar" src="' + n.avatar + '">' +
        '<div class="body"><div class="text"><b>' + n.user + '</b> ' + n.action + '<br><span style="color:var(--text-2)">“' + n.target + '”</span></div>' +
        '<div class="time">' + T.timeAgo(n.date) + '</div></div></div>';
    }).join("");
    box.querySelectorAll(".notif-item").forEach(function (el) {
      el.addEventListener("click", function () {
        const n = d.notifications.find(function (x) { return x.targetUrl === el.dataset.url; });
        if (n) n.read = true;
        T.save(); renderNotifications();
        location.href = el.dataset.url;
      });
      el.addEventListener("dblclick", function (e) { e.stopPropagation(); });
    });
  }

  /* ========== System settings ========== */
  function renderSettings() {
    const wrap = $("#panel-settings");
    if (!wrap) return;
    const d = T.load();
    const s = d.settings;
    if (wrap.dataset.built) return;

    wrap.innerHTML =
      '<div class="settings-grid">' +

      /* Appearance */
      '<div class="settings-card">' +
      '<h4>🎨 外观</h4><div class="desc">主题色、头像、Logo 与横幅</div>' +
      '<div class="form-field"><label>主题色</label><div class="color-swatches" id="color-swatches">' +
      ["#5B8DEF", "#7C6CF0", "#2FB97B", "#F0A11F", "#E9564E", "#0EA5B7", "#F06292", "#3B82F6"].map(function (c) {
        return '<button class="color-swatch' + (s.primaryColor === c ? " selected" : "") + '" data-color="' + c + '" style="background:' + c + '"></button>';
      }).join("") +
      '</div></div>' +
      '<div class="form-field"><label>头像（data URI 或地址）</label><br><img class="upload-preview" src="' + s.avatar + '" id="avatar-preview"><br>' +
      '<input id="set-avatar" value="' + (s.avatar || "").slice(0, 80) + '…" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)"><br>' +
      '<button class="btn btn-ghost btn-sm" style="margin-top:8px" id="avatar-upload">上传新头像</button></div>' +
      '<div class="form-field"><label>Logo 文字</label><input id="set-logo" value="' + s.logoText + '" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)"></div>' +
      '<div class="form-field"><label>背景图（data URI 或留空使用默认）</label><input id="set-banner" value="' + (s.banner || "") + '" placeholder="背景图片地址" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)"></div>' +
      '<button class="btn btn-primary btn-sm" id="save-appearance">保存外观</button>' +
      '</div>' +

      /* Website info */
      '<div class="settings-card">' +
      '<h4>🌐 网站信息</h4><div class="desc">站点标题、描述、页脚与公告</div>' +
      '<div class="form-field"><label>站点标题</label><input id="set-title" value="' + s.siteTitle + '" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)"></div>' +
      '<div class="form-field"><label>描述</label><input id="set-desc" value="' + s.description + '" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)"></div>' +
      '<div class="form-field"><label>页脚文字</label><input id="set-footer" value="' + s.footer + '" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)"></div>' +
      '<div class="form-field"><label>公告</label><textarea id="set-announce" rows="3" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)">' + s.announcement + '</textarea></div>' +
      '<button class="btn btn-primary btn-sm" id="save-info">保存信息</button>' +
      '</div>' +

      /* Email */
      '<div class="settings-card">' +
      '<h4>📧 邮件通知</h4><div class="desc">SMTP 服务与消息提醒</div>' +
      '<div class="switch-row"><span>启用邮件通知</span><span class="switch' + (s.emailNotif.enabled ? " on" : "") + '" id="set-email-on"></span></div>' +
      '<div class="switch-row"><span>收到留言时提醒</span><span class="switch' + (s.emailNotif.notifyOnMessage ? " on" : "") + '" id="set-email-msg"></span></div>' +
      '<div class="switch-row"><span>收到评论时提醒</span><span class="switch' + (s.emailNotif.notifyOnComment ? " on" : "") + '" id="set-email-cmt"></span></div>' +
      '<div class="form-field" style="margin-top:14px"><label>SMTP 服务器</label><input id="set-smtp-host" value="' + s.smtp.host + '" placeholder="smtp.example.com" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)"></div>' +
      '<div class="form-field"><label>端口</label><input id="set-smtp-port" value="' + s.smtp.port + '" placeholder="465" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)"></div>' +
      '<div class="form-field"><label>账号</label><input id="set-smtp-user" value="' + s.smtp.user + '" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)"></div>' +
      '<div class="form-field"><label>密码</label><input type="password" id="set-smtp-pass" value="' + s.smtp.pass + '" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)"></div>' +
      '<div class="form-field"><label>通知邮箱</label><input id="set-smtp-to" value="' + s.emailNotif.notifyEmail + '" placeholder="you@example.com" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)"></div>' +
      '<button class="btn btn-primary btn-sm" id="save-email">保存配置</button>' +
      '</div>' +

      /* Security */
      '<div class="settings-card">' +
      '<h4>🔒 安全</h4><div class="desc">密码、登录与会话设置</div>' +
      '<div class="switch-row"><span>允许登录</span><span class="switch' + (s.security.loginEnabled ? " on" : "") + '" id="set-login-on"></span></div>' +
      '<div class="switch-row"><span>会话时长</span><span style="font-size:13px;color:var(--text-2)"><input id="set-session" type="number" min="1" max="720" value="' + s.security.sessionHours + '" style="width:70px;border:1px solid var(--border);border-radius:var(--r-sm);padding:6px 10px;background:var(--surface)"> 小时</span></div>' +
      '<div class="form-field" style="margin-top:14px"><label>修改密码</label><input type="password" id="set-pwd-old" placeholder="当前密码" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface);margin-bottom:8px"><input type="password" id="set-pwd-new" placeholder="新密码" style="width:100%;border:1px solid var(--border);border-radius:var(--r-sm);padding:9px 12px;background:var(--surface)"></div>' +
      '<button class="btn btn-primary btn-sm" id="save-security">保存安全设置</button>' +
      '<button class="btn btn-ghost btn-sm" id="reset-data" style="margin-left:8px">恢复示例数据</button>' +
      '</div>' +
      '</div>';

    /* color swatches */
    $$("#color-swatches .color-swatch").forEach(function (c) {
      c.addEventListener("click", function () {
        $$("#color-swatches .color-swatch").forEach(function (x) { x.classList.remove("selected"); });
        c.classList.add("selected");
      });
    });

    /* avatar upload */
    $("#avatar-upload").addEventListener("click", function () {
      const input = document.createElement("input");
      input.type = "file"; input.accept = "image/*";
      input.onchange = function () {
        const f = input.files[0];
        if (!f || f.size > 1.5 * 1024 * 1024) return toast("图片请控制在 1.5MB 以内", "error");
        const r = new FileReader();
        r.onload = function () { $("#avatar-preview").src = r.result; $("#set-avatar").value = r.result; toast("头像已选择，保存后生效"); };
        r.readAsDataURL(f);
      };
      input.click();
    });

    /* switches */
    function bindSwitch(id, onToggle) {
      const el = $(id);
      if (!el) return;
      el.addEventListener("click", function () { el.classList.toggle("on"); onToggle && onToggle(el.classList.contains("on")); });
    }
    bindSwitch("#set-email-on");
    bindSwitch("#set-email-msg");
    bindSwitch("#set-email-cmt");
    bindSwitch("#set-login-on");

    $("#save-appearance").addEventListener("click", function () {
      const sel = $("#color-swatches .color-swatch.selected");
      if (sel) s.primaryColor = sel.dataset.color;
      const av = $("#set-avatar").value;
      if (av && av !== s.avatar) s.avatar = av;
      s.logoText = $("#set-logo").value || "Tnine";
      s.banner = $("#set-banner").value;
      T.save();
      // apply live
      document.documentElement.style.setProperty("--primary", s.primaryColor);
      document.documentElement.style.setProperty("--primary-grad", "linear-gradient(135deg, " + s.primaryColor + " 0%, #7C6CF0 100%)");
      toast("外观已保存");
    });
    $("#save-info").addEventListener("click", function () {
      s.siteTitle = $("#set-title").value || "Tnine";
      s.description = $("#set-desc").value;
      s.footer = $("#set-footer").value;
      s.announcement = $("#set-announce").value;
      T.save(); toast("网站信息已保存");
    });
    $("#save-email").addEventListener("click", function () {
      s.emailNotif.enabled = $("#set-email-on").classList.contains("on");
      s.emailNotif.notifyOnMessage = $("#set-email-msg").classList.contains("on");
      s.emailNotif.notifyOnComment = $("#set-email-cmt").classList.contains("on");
      s.smtp.host = $("#set-smtp-host").value;
      s.smtp.port = $("#set-smtp-port").value;
      s.smtp.user = $("#set-smtp-user").value;
      s.smtp.pass = $("#set-smtp-pass").value;
      s.emailNotif.notifyEmail = $("#set-smtp-to").value;
      T.save(); toast("邮件配置已保存");
    });
    $("#save-security").addEventListener("click", function () {
      s.security.loginEnabled = $("#set-login-on").classList.contains("on");
      s.security.sessionHours = parseInt($("#set-session").value, 10) || 24;
      const oldPwd = $("#set-pwd-old").value;
      const newPwd = $("#set-pwd-new").value;
      if (oldPwd || newPwd) {
        if (oldPwd !== s.security.password) return toast("当前密码不正确", "error");
        if (newPwd.length < 6) return toast("新密码至少 6 位", "error");
        s.security.password = newPwd;
        toast("密码已修改");
      }
      T.save();
      if (!oldPwd && !newPwd) toast("安全设置已保存");
    });
    $("#reset-data").addEventListener("click", function () {
      openConfirm("恢复示例数据", "将重置所有内容为初始示例数据，且清空登录密码为 admin123，确定吗？", function () {
        T.reset(); location.reload();
      });
    });
    wrap.dataset.built = "1";
  }

  /* ========== Confirm / Prompt modals ========== */
  function openConfirm(title, text, onOk) {
    const mask = document.createElement("div");
    mask.className = "modal-mask open";
    mask.innerHTML =
      '<div class="modal">' +
      '<div class="modal-title">' + title + '</div>' +
      '<div class="modal-sub">' + text + '</div>' +
      '<div class="modal-actions">' +
      '<button class="btn btn-ghost" data-cancel>取消</button>' +
      '<button class="btn btn-primary" data-ok>确认执行</button>' +
      '</div></div>';
    document.body.appendChild(mask);
    mask.querySelector("[data-cancel]").addEventListener("click", function () { mask.remove(); });
    mask.querySelector("[data-ok]").addEventListener("click", function () { mask.remove(); onOk(); });
    mask.addEventListener("click", function (e) { if (e.target === mask) mask.remove(); });
  }
  function openPrompt(title, text, onOk) {
    const mask = document.createElement("div");
    mask.className = "modal-mask open";
    mask.innerHTML =
      '<div class="modal">' +
      '<div class="modal-title">' + title + '</div>' +
      '<div class="modal-sub">' + text + '</div>' +
      '<textarea id="prompt-input" rows="3" placeholder="输入内容…" style="width:100%;border:1px solid var(--border);border-radius:var(--r-md);padding:10px 12px;background:var(--surface)"></textarea>' +
      '<div class="modal-actions">' +
      '<button class="btn btn-ghost" data-cancel>取消</button>' +
      '<button class="btn btn-primary" data-ok>确定</button>' +
      '</div></div>';
    document.body.appendChild(mask);
    const input = mask.querySelector("#prompt-input");
    setTimeout(function () { input.focus(); }, 60);
    mask.querySelector("[data-cancel]").addEventListener("click", function () { mask.remove(); });
    mask.querySelector("[data-ok]").addEventListener("click", function () { mask.remove(); onOk(input.value); });
    mask.addEventListener("click", function (e) { if (e.target === mask) mask.remove(); });
  }
  window.openConfirm = openConfirm;

  /* ========== Init ========== */
  document.addEventListener("DOMContentLoaded", function () {
    // theme from settings
    const s = T.load().settings;
    document.documentElement.setAttribute("data-theme", s.theme === "dark" ? "dark" : "light");
    document.documentElement.style.setProperty("--primary", s.primaryColor);
    document.documentElement.style.setProperty("--primary-grad", "linear-gradient(135deg, " + s.primaryColor + " 0%, #7C6CF0 100%)");
    initAuth();
    bindNav();
    if (T.isLoggedIn()) {
      renderDashboard();
      // default active panel
      const first = $("#panel-dashboard");
      if (first) first.classList.add("active");
      $("#panel-title").textContent = "仪表盘";
    }
  });
})();
