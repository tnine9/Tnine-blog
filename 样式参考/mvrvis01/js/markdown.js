/* ============================================================
   Tnine · Markdown Parser + Code Highlighter
   自包含实现，无外部依赖，file:// 协议可用
   ============================================================ */
(function () {
  "use strict";

  /* ---------- Tokenizer helpers ---------- */
  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function inline(text) {
    // code spans
    text = text.replace(/`([^`\n]+)`/g, function (_, code) {
      return '<code>' + escapeHtml(code) + '</code>';
    });
    // images ![alt](src)
    text = text.replace(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)/g, function (_, alt, src, title) {
      return '<img src="' + escapeHtml(src) + '" alt="' + escapeHtml(alt || "") + '"' + (title ? ' title="' + escapeHtml(title) + '"' : "") + '/>';
    });
    // links [text](href)
    text = text.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)/g, function (_, label, href, title) {
      return '<a href="' + escapeHtml(href) + '"' + (title ? ' title="' + escapeHtml(title) + '"' : "") + '>' + label + '</a>';
    });
    // bold / italic
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/__([^_]+)__/g, '<strong>$1</strong>');
    text = text.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
    text = text.replace(/(^|[^_])_([^_\n]+)_(?!_)/g, '$1<em>$2</em>');
    return text;
  }

  /* ---------- Simple code highlighter ---------- */
  const KEYWORDS = {
    js: ["const","let","var","function","return","if","else","for","while","class","new","this","async","await","import","export","from","try","catch","throw","typeof","instanceof","in","of","null","undefined","true","false","switch","case","break","continue","default","extends","super","static","get","set","yield","delete"],
    ts: ["const","let","var","function","return","if","else","for","while","class","interface","type","new","this","async","await","import","export","from","try","catch","throw","typeof","instanceof","in","of","null","undefined","true","false","switch","case","break","continue","default","extends","implements","super","readonly","enum","namespace","declare","keyof","infer","never","any","unknown","string","number","boolean"],
    py: ["def","return","if","elif","else","for","while","import","from","class","try","except","finally","with","as","lambda","pass","break","continue","global","nonlocal","yield","raise","assert","async","await","None","True","False","and","or","not","in","is"],
    css: ["@media","@keyframes","@import","@font-face","@supports",":root","body","html","div","span"],
    html: ["html","head","body","div","span","class","id","style"]
  };

  function highlight(code, lang) {
    const l = (lang || "").toLowerCase();
    let kw = KEYWORDS.js;
    if (l === "ts" || l === "typescript") kw = KEYWORDS.ts;
    else if (l === "py" || l === "python") kw = KEYWORDS.py;
    else if (l === "css") kw = KEYWORDS.css;

    const esc = escapeHtml(code);
    let out = esc;
    // comments (line) - apply first, protect them
    out = out.replace(/(\/\/[^\n]*)/g, '<span class="hl-com">$1</span>');
    out = out.replace(/(#[^\n]*)/g, '<span class="hl-com">$1</span>');
    // strings
    out = out.replace(/(['"`][^'"`\n]*['"`])/g, '<span class="hl-str">$1</span>');
    // numbers
    out = out.replace(/(\b\d+(?:\.\d+)?\b)/g, '<span class="hl-num">$1</span>');
    // keywords
    kw.sort(function (a, b) { return b.length - a.length; });
    out = out.replace(new RegExp("\\b(" + kw.join("|") + ")\\b", "g"), '<span class="hl-kw">$1</span>');
    // functions
    out = out.replace(/([a-zA-Z_$][\w$]*)(\s*\()/g, '<span class="hl-fn">$1</span>$2');
    return out;
  }

  /* ---------- Block parser ---------- */
  function parseMarkdown(src) {
    if (!src) return "";
    const lines = String(src).replace(/\r\n/g, "\n").split("\n");
    let html = "";
    let i = 0;
    let listStack = [];

    function closeList() {
      if (listStack.length) {
        html += "</li></ul>";
        listStack = [];
      }
    }

    while (i < lines.length) {
      const line = lines[i];

      // blank line
      if (/^\s*$/.test(line)) { closeList(); i++; continue; }

      // fenced code block
      const fence = line.match(/^```(\w*)\s*$/);
      if (fence) {
        closeList();
        const lang = fence[1];
        const buf = [];
        i++;
        while (i < lines.length && !/^```\s*$/.test(lines[i])) { buf.push(lines[i]); i++; }
        i++; // skip closing fence
        html += '<pre><span class="lang-tag">' + escapeHtml(lang || "code") + '</span><code>' + highlight(buf.join("\n"), lang) + '</code></pre>';
        continue;
      }

      // headings
      const h = line.match(/^(#{1,4})\s+(.*)$/);
      if (h) {
        closeList();
        const lv = h[1].length;
        const txt = h[2].replace(/\s*#+\s*$/, "");
        html += '<h' + lv + '>' + inline(escapeHtml(txt)) + '</h' + lv + '>';
        i++;
        continue;
      }

      // horizontal rule
      if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) { closeList(); html += "<hr>"; i++; continue; }

      // blockquote
      if (/^>\s?/.test(line)) {
        closeList();
        const buf = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) { buf.push(lines[i].replace(/^>\s?/, "")); i++; }
        html += "<blockquote>" + inline(escapeHtml(buf.join(" "))) + "</blockquote>";
        continue;
      }

      // unordered list
      if (/^[-*+]\s+/.test(line)) {
        const item = line.replace(/^[-*+]\s+/, "");
        if (!listStack.length) { html += "<ul>"; listStack.push("ul"); }
        html += "<li>" + inline(escapeHtml(item));
        // inline continuation if next line is indented
        while (i + 1 < lines.length && /^(\s{2,}|\t)/.test(lines[i + 1]) && !/^[-*+]\s+/.test(lines[i + 1]) && !/^\d+\.\s+/.test(lines[i + 1]) && !/^```/.test(lines[i + 1])) {
          i++;
          html += "<br>" + inline(escapeHtml(lines[i].trim()));
        }
        html += "</li>";
        i++;
        continue;
      }

      // ordered list
      if (/^\d+\.\s+/.test(line)) {
        const item = line.replace(/^\d+\.\s+/, "");
        if (!listStack.length) { html += "<ol>"; listStack.push("ol"); }
        html += "<li>" + inline(escapeHtml(item)) + "</li>";
        i++;
        continue;
      }

      // table
      if (line.includes("|") && i + 1 < lines.length && /^\s*\|?[\s:-|]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes("-")) {
        closeList();
        const parseRow = function (r) {
          return r.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(function (c) { return c.trim(); });
        };
        const head = parseRow(line);
        i += 2; // skip header + separator
        const rows = [];
        while (i < lines.length && lines[i].includes("|")) { rows.push(parseRow(lines[i])); i++; }
        let t = "<table><thead><tr>";
        head.forEach(function (c) { t += "<th>" + inline(escapeHtml(c)) + "</th>"; });
        t += "</tr></thead><tbody>";
        rows.forEach(function (r) {
          t += "<tr>";
          for (let k = 0; k < head.length; k++) t += "<td>" + inline(escapeHtml(r[k] || "")) + "</td>";
          t += "</tr>";
        });
        t += "</tbody></table>";
        html += t;
        continue;
      }

      // paragraph
      closeList();
      let p = line;
      while (i + 1 < lines.length && !/^\s*$/.test(lines[i + 1]) &&
             !/^(#{1,4}\s|```|>\s?|[-*+]\s+|\d+\.\s+)/.test(lines[i + 1])) {
        i++;
        p += "\n" + lines[i];
      }
      html += "<p>" + inline(escapeHtml(p)).replace(/\n/g, "<br>") + "</p>";
      i++;
    }
    closeList();
    return html;
  }

  /* ---------- TOC extraction ---------- */
  function extractToc(md) {
    const lines = String(md || "").split("\n");
    const toc = [];
    lines.forEach(function (line) {
      const m = line.match(/^(#{2,4})\s+(.*)$/);
      if (m) {
        toc.push({ level: m[1].length, title: m[2].replace(/\s*#+\s*$/, "").trim(), id: null });
      }
    });
    toc.forEach(function (item, idx) { item.id = "toc-" + idx; });
    return toc;
  }

  window.Markdown = { parse: parseMarkdown, highlight: highlight, extractToc: extractToc, inline: inline, escape: escapeHtml };
})();
