/*
 * Tnine 文章导航系统
 *
 * 功能：
 * 1. 从 Markdown 中提取标题
 * 2. 编辑文章时实时生成右侧目录
 * 3. 阅读文章时根据 HTML 标题生成目录
 * 4. 点击目录定位到对应标题
 * 5. 阅读文章时自动高亮当前章节
 * 6. EasyMDE 全屏时保持右侧导航
 */


/* =========================================================
   Markdown 标题解析
   ========================================================= */

function extractMarkdownHeadings(markdownText) {

    const lines = markdownText.split("\n");

    const headings = [];

    for (const line of lines) {

        const match = line.match(
            /^(#{1,6})\s+(.+?)\s*#*\s*$/
        );

        if (!match) {
            continue;
        }

        const level = match[1].length;

        const text = match[2]
            .replace(/\*\*(.*?)\*\*/g, "$1")
            .replace(/\*(.*?)\*/g, "$1")
            .replace(/`(.*?)`/g, "$1")
            .trim();

        if (!text) {
            continue;
        }

        headings.push({
            level: level,
            text: text,
        });
    }

    return headings;
}


/* =========================================================
   创建目录
   ========================================================= */

function renderToc(
    container,
    headings,
    onClick
) {

    if (!container) {
        return;
    }

    container.innerHTML = "";


    /* 没有标题 */

    if (headings.length === 0) {

        const empty =
            document.createElement("div");

        empty.className = "toc-empty";

        empty.textContent =
            "暂无目录";

        container.appendChild(empty);

        return;
    }


    /* 标题 */

    const title =
        document.createElement("div");

    title.className = "toc-title";

    title.textContent =
        "文章目录";

    container.appendChild(title);


    /* 列表 */

    const list =
        document.createElement("div");

    list.className = "toc-list";


    headings.forEach(
        (heading, index) => {

            const item =
                document.createElement("button");

            item.type = "button";

            item.className =
                "toc-item";

            item.dataset.index =
                String(index);

            item.dataset.level =
                String(heading.level);

            item.textContent =
                heading.text;


            item.addEventListener(
                "click",
                function () {

                    if (
                        typeof onClick ===
                        "function"
                    ) {
                        onClick(
                            heading,
                            index
                        );
                    }

                }
            );


            list.appendChild(item);
        }
    );


    container.appendChild(list);
}


/* =========================================================
   设置当前导航高亮
   ========================================================= */

function setActiveTocItem(
    container,
    activeIndex
) {

    if (!container) {
        return;
    }

    const items =
        container.querySelectorAll(
            ".toc-item"
        );

    items.forEach(
        (item, index) => {

            item.classList.toggle(
                "active",
                index === activeIndex
            );

        }
    );
}


/* =========================================================
   阅读文章 TOC
   ========================================================= */

function initArticleToc() {

    const article =
        document.querySelector(
            ".markdown-body"
        );

    const toc =
        document.querySelector(
            ".toc-container"
        );


    if (!article || !toc) {
        return;
    }


    const headings =
        Array.from(
            article.querySelectorAll(
                "h1, h2, h3, h4, h5, h6"
            )
        );


    if (headings.length === 0) {

        renderToc(
            toc,
            [],
            null
        );

        return;
    }


    /*
     * 给标题生成 ID
     */

    const items =
        headings.map(
            (heading, index) => {

                if (!heading.id) {

                    heading.id =
                        `article-heading-${index}`;
                }

                return {
                    level: Number(
                        heading.tagName.substring(1)
                    ),

                    text:
                        heading.textContent.trim(),

                    element: heading,
                };
            }
        );


    /*
     * 创建目录
     */

    renderToc(
        toc,
        items,
        function (heading) {

            heading.element.scrollIntoView({
                behavior: "smooth",
                block: "start",
            });

        }
    );


    /*
     * 文章滚动时自动高亮
     */

    function updateActiveHeading() {

        let activeIndex = 0;


        headings.forEach(
            (heading, index) => {

                const rect =
                    heading.getBoundingClientRect();

                if (
                    rect.top <= 160
                ) {
                    activeIndex = index;
                }

            }
        );


        setActiveTocItem(
            toc,
            activeIndex
        );
    }


    window.addEventListener(
        "scroll",
        updateActiveHeading,
        {
            passive: true,
        }
    );


    updateActiveHeading();
}


/* =========================================================
   编辑器 TOC
   ========================================================= */

function initMarkdownEditorToc() {

    const toc =
        document.querySelector(
            ".toc-container"
        );

    const editor =
        window.tnineMarkdownEditor;


    /*
     * 当前页面不是 Markdown 编辑页
     */

    if (!toc || !editor) {
        return;
    }


    /*
     * 根据 Markdown 内容生成目录
     */

    function refreshToc() {

        const markdownText =
            editor.value();


        const headings =
            extractMarkdownHeadings(
                markdownText
            );


        /*
         * 编辑器目录仅展示 h1-h4 层级
         */

        const filtered =
            headings.filter(
                function (heading) {

                    return (
                        heading.level >= 1 &&
                        heading.level <= 4
                    );
                }
            );


        renderToc(
            toc,
            filtered,
            function (
                heading,
                headingIndex
            ) {

                /*
                 * 优先在预览面板中定位标题；
                 * 预览区不可用或未命中时，
                 * 回退到编辑区 CodeMirror 定位
                 */

                if (
                    !focusPreviewHeading(
                        heading
                    )
                ) {

                    focusEditorHeading(
                        editor,
                        headingIndex
                    );
                }

            }
        );
    }


    /*
     * 在实时预览面板中滚动到对应标题
     */

    function focusPreviewHeading(heading) {

        const preview =
            document.getElementById(
                "editorPreviewBody"
            );

        if (!preview) {
            return false;
        }

        const candidates =
            preview.querySelectorAll(
                "h1, h2, h3, h4"
            );

        for (
            const element of candidates
        ) {

            if (
                element.textContent
                    .trim() ===
                heading.text
            ) {

                element.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                });

                return true;
            }
        }

        return false;
    }


    /*
     * 点击目录后，
     * 在 CodeMirror 中定位 Markdown 标题
     */

    function focusEditorHeading(
        editorInstance,
        headingIndex
    ) {

        const lines =
            editorInstance
                .value()
                .split("\n");


        let currentHeadingIndex = 0;


        for (
            let lineIndex = 0;
            lineIndex < lines.length;
            lineIndex++
        ) {

            const match =
                lines[lineIndex].match(
                    /^(#{1,6})\s+(.+?)\s*#*\s*$/
                );


            if (!match) {
                continue;
            }


            if (
                currentHeadingIndex ===
                headingIndex
            ) {

                editorInstance.codemirror.setCursor(
                    lineIndex,
                    0
                );


                editorInstance.codemirror.scrollIntoView(
                    {
                        line: lineIndex,
                        ch: 0,
                    },
                    120
                );


                editorInstance.codemirror.focus();

                return;
            }


            currentHeadingIndex++;
        }
    }


    /*
     * 首次生成
     */

    refreshToc();


    /*
     * Markdown 内容改变时实时更新
     */

    editor.codemirror.on(
        "change",
        function () {

            refreshToc();

        }
    );
}


/* =========================================================
   全屏导航
   ========================================================= */

function updateFullscreenToc() {

    const toc =
        document.querySelector(
            ".toc-container"
        );


    if (!toc) {
        return;
    }


    /*
     * EasyMDE 全屏状态
     */

    const fullscreenEditor =
        document.querySelector(
            ".CodeMirror-fullscreen"
        );


    if (fullscreenEditor) {

        toc.classList.add(
            "toc-fullscreen"
        );

    } else {

        toc.classList.remove(
            "toc-fullscreen"
        );
    }
}


/* =========================================================
   暴露给页面
   ========================================================= */

window.initMarkdownEditorToc =
    initMarkdownEditorToc;


/* =========================================================
   页面初始化
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        /*
         * 阅读文章页
         */
        initArticleToc();


        /*
         * 检查 EasyMDE 全屏状态
         *
         * 这里不直接初始化编辑器，
         * 因为 EasyMDE 是由 admin_new.html /
         * admin_edit.html 创建的。
         */
        setInterval(
            updateFullscreenToc,
            300
        );

    }
);