/* ============================================================
   Tnine · Data Layer
   种子数据 + localStorage 持久化 + 工具函数
   ============================================================ */
(function () {
  "use strict";

  const STORAGE_KEY = "tnine_data_v1";

  /* ---------- SVG helpers (avoid external deps) ---------- */
  function svgAvatar(name, seed) {
    const palette = [
      ["#5B8DEF", "#7C6CF0"], ["#2FB97B", "#4CD9A8"], ["#F0A11F", "#F7C948"],
      ["#E9564E", "#F0806E"], ["#7C6CF0", "#B08CF8"], ["#0EA5B7", "#38D6E6"],
      ["#F06292", "#FA96B8"], ["#64748B", "#94A3B8"]
    ];
    const c = palette[(seed || name.length) % palette.length];
    const ch = (name || "?").trim().charAt(0).toUpperCase();
    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">' +
      '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">' +
      '<stop offset="0" stop-color="' + c[0] + '"/><stop offset="1" stop-color="' + c[1] + '"/>' +
      '</linearGradient></defs>' +
      '<rect width="96" height="96" rx="22" fill="url(#g)"/>' +
      '<text x="48" y="60" font-family="Inter,-apple-system,sans-serif" font-size="40" font-weight="700" fill="#fff" text-anchor="middle">' + ch + '</text></svg>';
    return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  }

  function svgCover(title, seed) {
    const hues = [
      ["#5B8DEF", "#7C6CF0", "#8FB0F7"], ["#2FB97B", "#0EA5B7", "#6FE0A8"],
      ["#F0A11F", "#E9564E", "#F7C948"], ["#7C6CF0", "#5B8DEF", "#B08CF8"],
      ["#0EA5B7", "#2FB97B", "#38D6E6"], ["#E9564E", "#F06292", "#F0806E"]
    ];
    const c = hues[(seed || title.length) % hues.length];
    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450">' +
      '<defs><linearGradient id="c" x1="0" y1="0" x2="1" y2="1">' +
      '<stop offset="0" stop-color="' + c[0] + '"/><stop offset="0.55" stop-color="' + c[1] + '"/>' +
      '<stop offset="1" stop-color="' + c[2] + '"/></linearGradient></defs>' +
      '<rect width="800" height="450" fill="url(#c)"/>' +
      '<circle cx="120" cy="90" r="180" fill="rgba(255,255,255,.08)"/>' +
      '<circle cx="700" cy="380" r="220" fill="rgba(255,255,255,.07)"/>' +
      '<circle cx="640" cy="60" r="70" fill="rgba(255,255,255,.10)"/>' +
      '<rect x="0" y="330" width="800" height="120" fill="rgba(255,255,255,.06)"/>' +
      '<text x="56" y="150" font-family="Inter,-apple-system,sans-serif" font-size="19" font-weight="600" fill="rgba(255,255,255,.85)">TNINE</text>' +
      '</svg>';
    return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  }

  /* ---------- Date helpers ---------- */
  function fmtDate(ts) {
    const d = new Date(ts);
    return d.getFullYear() + "." + String(d.getMonth() + 1).padStart(2, "0") + "." + String(d.getDate()).padStart(2, "0");
  }
  function fmtDateTime(ts) {
    const d = new Date(ts);
    return fmtDate(ts) + " " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  }
  function timeAgo(ts) {
    const diff = Date.now() - ts;
    const m = Math.floor(diff / 60000);
    if (m < 1) return "刚刚";
    if (m < 60) return m + " 分钟前";
    const h = Math.floor(m / 60);
    if (h < 24) return h + " 小时前";
    const d = Math.floor(h / 24);
    if (d < 30) return d + " 天前";
    const mo = Math.floor(d / 30);
    if (mo < 12) return mo + " 个月前";
    return Math.floor(mo / 12) + " 年前";
  }
  function daysAgo(n, hour) {
    const d = new Date();
    d.setDate(d.getDate() - n);
    d.setHours(hour || 10, Math.floor(Math.random() * 50) + 5, 0, 0);
    return d.getTime();
  }
  function iso(ts) { return new Date(ts).toISOString(); }

  /* ---------- Random ---------- */
  function randPick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

  /* ---------- Seed data ---------- */
  const MARKDOWN_DEMO =
    "## 为什么需要个人博客\n\n" +
    "在信息爆炸的时代，拥有一个**属于自己的数字花园**，是一种回归。它不追求流量，只在乎沉淀。\n\n" +
    "> 记录技术、生活和思考 —— 这是我写博客的初衷。\n\n" +
    "## 系统架构\n\n" +
    "整个系统分为四个部分：\n\n" +
    "1. **前端网站**：首页、文章、朋友圈、留言\n" +
    "2. **管理后台**：博客 / 朋友圈 / 留言 / 通知 / 系统管理\n" +
    "3. **设计系统**：亮色暗色主题、可配置主色、4px 间距体系\n" +
    "4. **数据层**：本地持久化，离线可用\n\n" +
    "## 核心代码示例\n\n" +
    "```js\n" +
    "// 渲染时间线：混合文章、朋友圈与留言\n" +
    "function buildTimeline(items) {\n" +
    "  return items\n" +
    "    .sort((a, b) => b.date - a.date)\n" +
    "    .map(item => renderTimelineCard(item));\n" +
    "}\n" +
    "\n" +
    "const timeline = buildTimeline([\n" +
    "  { type: 'article', title: '如何设计一个个人博客系统', date: 1755206400000 },\n" +
    "  { type: 'moment',  text: '今天完成了新的功能',       date: 1755120000000 }\n" +
    "]);\n" +
    "```\n\n" +
    "## 设计原则\n\n" +
    "| 原则 | 说明 |\n" +
    "| --- | --- |\n" +
    "| 极简 | 只保留必要元素 |\n" +
    "| 优雅 | 细腻动效与留白 |\n" +
    "| 温暖 | 像朋友圈一样真实 |\n" +
    "| 可维护 | 长期更新不费力 |\n\n" +
    "## 结语\n\n" +
    "好的工具应当服务于长期主义。这个博客系统会陪我很多年，也希望能启发你搭建自己的数字花园。";

  function seedArticles() {
    const now = Date.now();
    return [
      {
        id: "a1", title: "如何设计一个个人博客系统", status: "published",
        summary: "从信息架构、设计语言到 CMS 能力，分享设计 Tnine 的完整思考：一个极简、优雅、可长期维护的数字花园。",
        category: "技术", tags: ["设计", "博客", "系统"], date: daysAgo(0),
        readTime: 8, views: 1286, content: MARKDOWN_DEMO
      },
      {
        id: "a2", title: "2026 年技术趋势漫谈：AI 与个人开发者", status: "published",
        summary: "大模型正在改变每个人的工作流。聊聊 AI 编程、智能体与个人开发者的新机会。",
        category: "思考", tags: ["AI", "趋势"], date: daysAgo(6),
        readTime: 6, views: 942, content:
          "## 从工具到伙伴\n\n2026 年，AI 已经不是“玩具”。它正在成为**个人开发者的杠杆**。\n\n> 一个人 + AI，可以抵得上一个小团队。\n\n## 几个观察\n\n- 代码生成只是起点，**需求理解**才是新护城河\n- 智能体让“自动化”变成“自主化”\n- 个人品牌 + AI 工具 = 超级个体\n\n## 保持清醒\n\n技术浪潮里，唯一不变的是**持续学习和深度思考**。"
      },
      {
        id: "a3", title: "我的极简生活主义：少即是多", status: "published",
        summary: "减少不必要的拥有，把注意力留给真正重要的事。分享我的极简原则与整理方法。",
        category: "生活", tags: ["极简", "生活方式"], date: daysAgo(13),
        readTime: 5, views: 756, content:
          "## 为什么开始极简\n\n生活被物品填满的时候，**注意力也被填满了**。\n\n### 三个原则\n\n1. 一进一出\n2. 常用即收纳\n3. 犹豫 = 不需要\n\n> 拥有更少，体验更多。"
      },
      {
        id: "a4", title: "TypeScript 类型体操：从入门到装逼", status: "published",
        summary: "用几个经典类型题，掌握 infer、递归与模板字面量类型，感受类型系统的优雅。",
        category: "技术", tags: ["TypeScript", "前端"], date: daysAgo(20),
        readTime: 10, views: 2103, content:
          "## 什么是类型体操\n\n类型体操 = 用类型系统写“程序”。\n\n```ts\n// 提取数组元素类型\ntype ElementOf<T extends any[]> = T extends (infer E)[] ? E : never;\n\ntype A = ElementOf<[string, number]>; // string | number\n```\n\n## 经典题：实现 DeepReadonly\n\n```ts\ntype DeepReadonly<T> = T extends Record<string, any>\n  ? { readonly [K in keyof T]: DeepReadonly<T[K]> }\n  : T;\n```\n\n## 小结\n\n类型系统不是炫技，它让你的**重构更安全、文档更鲜活**。"
      },
      {
        id: "a5", title: "读书笔记：《设计中的设计》", status: "draft",
        summary: "原研哉对“空”与“白”的思考，重新理解设计之于生活的意义。（草稿）",
        category: "阅读", tags: ["读书", "设计"], date: daysAgo(2),
        readTime: 4, views: 0, content:
          "## 关于空白\n\n> 设计不是创造新东西，而是重新认识已知。\n\n草稿中，敬请期待。"
      }
    ];
  }

  function seedMoments() {
    const visitors = ["小明", "阿May", "老张", "Coco", "林深", "Nancy", "Kevin", "紫涵", "大熊"];
    const now = Date.now();
    return [
      {
        id: "m1", text: "今天完成了新的功能：朋友圈支持评论回复了。开发的过程像种花，一点点浇灌。",
        images: [], date: daysAgo(1, 21), likes: [{ name: "小明" }, { name: "Coco" }, { name: "老张" }, { name: "Nancy" }],
        comments: [
          { name: "小明", text: "太强了，等上线！", time: daysAgo(1, 22), replyTo: null },
          { name: "Coco", text: "期待这个功能很久了", time: daysAgo(1, 23), replyTo: null }
        ]
      },
      {
        id: "m2", text: "周末去山里徒步，云海真的很治愈。相机里存了 200 张照片，先放三张。",
        images: [svgCover("山", 1), svgCover("云", 2), svgCover("路", 3)], date: daysAgo(3, 16),
        likes: [{ name: "阿May" }, { name: "林深" }, { name: "Kevin" }, { name: "紫涵" }, { name: "大熊" }, { name: "小明" }],
        comments: [
          { name: "阿May", text: "哪里！求攻略", time: daysAgo(3, 17), replyTo: null },
          { name: "林深", text: "云海也太漂亮了吧", time: daysAgo(3, 18), replyTo: "阿May" },
          { name: "老张", text: "下次带上我", time: daysAgo(2, 9), replyTo: null },
          { name: "Kevin", text: "已收藏，下次去", time: daysAgo(2, 10), replyTo: null }
        ]
      },
      {
        id: "m3", text: "深夜写代码的正确姿势：一杯热茶 + 一首歌 + 一盏暖灯。",
        images: [], date: daysAgo(5, 23), likes: [{ name: "Nancy" }, { name: "大熊" }],
        comments: [{ name: "Nancy", text: "注意身体呀", time: daysAgo(5, 23), replyTo: null }]
      },
      {
        id: "m4", text: "读完《设计中的设计》，最大的感受是：设计是生活方式的表达，而不仅是视觉。",
        images: [svgCover("书", 7)], date: daysAgo(8, 20),
        likes: [{ name: "紫涵" }, { name: "林深" }, { name: "Coco" }],
        comments: []
      },
      {
        id: "m5", text: "个人博客系统 Tnine 正式开源规划中，这是一个只属于自己的数字花园。",
        images: [], date: daysAgo(11, 12), likes: [{ name: "小明" }, { name: "老张" }, { name: "阿May" }, { name: "Kevin" }],
        comments: [
          { name: "老张", text: "支持！", time: daysAgo(11, 13), replyTo: null },
          { name: "小明", text: "前排围观", time: daysAgo(11, 14), replyTo: null },
          { name: "Kevin", text: "名字好听", time: daysAgo(11, 15), replyTo: null }
        ]
      }
    ];
  }

  function seedMessages() {
    return [
      {
        id: "msg1", nickname: "匿名访客", avatar: svgAvatar("匿", 3), content: "你好，很喜欢你的博客！设计得很精致。", date: daysAgo(1, 15), isPrivate: false, important: true,
        replies: [{ name: "Tnine", content: "谢谢你的喜欢，欢迎常来～", time: daysAgo(1, 18) }]
      },
      {
        id: "msg2", nickname: "前端爱好者", avatar: svgAvatar("前", 1), content: "请问时间线动画是怎么实现的？想学习一下。", date: daysAgo(2, 11), isPrivate: false, important: false,
        replies: [{ name: "Tnine", content: "用的是 IntersectionObserver + CSS transition，很简单也很顺滑。", time: daysAgo(2, 13) }]
      },
      {
        id: "msg3", nickname: "路过的小鹿", avatar: svgAvatar("鹿", 5), content: "暗色主题太舒服了，夜里看文章不刺眼。", date: daysAgo(4, 22), isPrivate: false, important: false, replies: []
      },
      {
        id: "msg4", nickname: "神秘人", avatar: svgAvatar("神", 7), content: "私密留言测试：这条只有站长能看到哦。", date: daysAgo(1, 9), isPrivate: true, important: false, replies: []
      }
    ];
  }

  function seedNotifications() {
    const now = Date.now();
    return [
      { id: "n1", type: "comment", user: "小明", avatar: svgAvatar("明", 1), action: "评论了你的文章", target: "如何设计一个个人博客系统", targetUrl: "article.html?id=a1", date: daysAgo(0, 10), read: false },
      { id: "n2", type: "like", user: "Coco", avatar: svgAvatar("C", 4), action: "点赞了你的朋友圈", target: "今天完成了新的功能：朋友圈支持评论回复了", targetUrl: "moments.html", date: daysAgo(1, 20), read: false },
      { id: "n3", type: "message", user: "匿名访客", avatar: svgAvatar("匿", 3), action: "给你留了一条言", target: "你好，很喜欢你的博客！", targetUrl: "messages.html", date: daysAgo(1, 15), read: false },
      { id: "n4", type: "comment", user: "Nancy", avatar: svgAvatar("N", 2), action: "评论了你的朋友圈", target: "深夜写代码的正确姿势", targetUrl: "moments.html", date: daysAgo(5, 23), read: true },
      { id: "n5", type: "like", user: "老张", avatar: svgAvatar("张", 6), action: "点赞了你的朋友圈", target: "周末去山里徒步", targetUrl: "moments.html", date: daysAgo(3, 19), read: true }
    ];
  }

  function seedSettings() {
    return {
      siteTitle: "Tnine", description: "记录技术、生活和思考", footer: "© 2026 Tnine · 用爱与代码浇灌的数字花园",
      announcement: "欢迎来到我的数字花园 🌱 这里记录技术、生活与思考。",
      primaryColor: "#5B8DEF", theme: "light", logoText: "Tnine",
      avatar: svgAvatar("T", 0), banner: null,
      smtp: { host: "", port: 465, user: "", pass: "", from: "" },
      emailNotif: { enabled: false, notifyOnMessage: true, notifyOnComment: true, notifyEmail: "" },
      security: { loginEnabled: true, sessionHours: 24, password: "admin123" }
    };
  }

  function seedStats() {
    const visits = [];
    for (let i = 29; i >= 0; i--) {
      const d = new Date(); d.setDate(d.getDate() - i);
      const key = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
      visits.push({ date: key, count: 30 + Math.floor(Math.random() * 60) + Math.floor(Math.abs(Math.sin(i * 1.7)) * 40) });
    }
    return { visits: visits };
  }

  function defaultData() {
    return {
      articles: seedArticles(),
      moments: seedMoments(),
      messages: seedMessages(),
      notifications: seedNotifications(),
      settings: seedSettings(),
      stats: seedStats()
    };
  }

  /* ---------- Store ---------- */
  let cache = null;
  function load() {
    if (cache) return cache;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        // merge with defaults to keep schema compatible
        const def = defaultData();
        cache = {
          articles: parsed.articles || def.articles,
          moments: parsed.moments || def.moments,
          messages: parsed.messages || def.messages,
          notifications: parsed.notifications || def.notifications,
          settings: Object.assign(def.settings, parsed.settings || {}),
          stats: Object.assign(def.stats, parsed.stats || {})
        };
      } else {
        cache = defaultData();
        save();
      }
    } catch (e) {
      cache = defaultData();
    }
    return cache;
  }
  function save() {
    if (!cache) return;
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(cache)); } catch (e) { /* storage full or blocked */ }
  }
  function reset() {
    cache = defaultData(); save();
    return cache;
  }

  /* ---------- Auth ---------- */
  const AUTH_KEY = "tnine_auth";
  function login(password) {
    const s = load().settings;
    if (s.security.loginEnabled === false) return { ok: false, msg: "登录功能已关闭" };
    if (password === s.security.password) {
      sessionStorage.setItem(AUTH_KEY, JSON.stringify({ name: "Tnine", time: Date.now() }));
      return { ok: true };
    }
    return { ok: false, msg: "密码错误" };
  }
  function logout() { sessionStorage.removeItem(AUTH_KEY); }
  function isLoggedIn() { return !!sessionStorage.getItem(AUTH_KEY); }
  function currentUser() {
    try { return JSON.parse(sessionStorage.getItem(AUTH_KEY) || "null"); } catch (e) { return null; }
  }

  /* ---------- Misc ---------- */
  function uid(prefix) { return prefix + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
  function readTimeOf(md) {
    const words = (md || "").replace(/```[\s\S]*?```/g, " ").length / 3;
    return Math.max(1, Math.round(words / 250));
  }
  function summaryOf(md, len) {
    const text = (md || "").replace(/[#*`>\[\]()!-]/g, " ").replace(/\s+/g, " ").trim();
    return text.length > len ? text.slice(0, len) + "…" : text;
  }
  function getArticle(id) { return load().articles.find(a => a.id === id); }

  /* ---------- Export ---------- */
  window.Tnine = {
    STORAGE_KEY: STORAGE_KEY,
    svgAvatar: svgAvatar, svgCover: svgCover,
    fmtDate: fmtDate, fmtDateTime: fmtDateTime, timeAgo: timeAgo,
    daysAgo: daysAgo, iso: iso, randPick: randPick,
    load: load, save: save, reset: reset,
    login: login, logout: logout, isLoggedIn: isLoggedIn, currentUser: currentUser,
    uid: uid, readTimeOf: readTimeOf, summaryOf: summaryOf, getArticle: getArticle
  };
})();
