/*
 * Tnine 代码复制功能
 *
 * 支持：
 * 1. 正式文章页面
 * 2. EasyMDE 普通预览
 * 3. EasyMDE 左右分屏预览
 */


/* =========================================================
   创建复制按钮
   ========================================================= */

function createCopyButton(pre) {

    if (
        pre.querySelector(
            ".code-copy-button"
        )
    ) {
        return;
    }


    const code =
        pre.querySelector("code");


    if (!code) {
        return;
    }


    const button =
        document.createElement("button");


    button.type = "button";

    button.className =
        "code-copy-button";

    button.textContent =
        "复制";


    button.addEventListener(
        "click",
        async function () {

            try {

                await navigator.clipboard.writeText(
                    code.innerText
                );


                button.textContent =
                    "已复制";


                button.classList.add(
                    "copied"
                );


                setTimeout(
                    function () {

                        button.textContent =
                            "复制";

                        button.classList.remove(
                            "copied"
                        );

                    },
                    1500
                );


            } catch (error) {

                console.error(
                    "复制代码失败：",
                    error
                );


                button.textContent =
                    "复制失败";
            }

        }
    );


    pre.appendChild(button);
}


/* =========================================================
   扫描代码块
   ========================================================= */

function scanCodeBlocks(container) {

    if (!container) {
        return;
    }


    const blocks =
        container.querySelectorAll(
            "pre"
        );


    blocks.forEach(
        function (pre) {

            createCopyButton(pre);

        }
    );
}


/* =========================================================
   初始化
   ========================================================= */

function initCodeCopy() {

    scanCodeBlocks(
        document.querySelector(
            ".markdown-body"
        )
    );


    scanCodeBlocks(
        document.querySelector(
            ".editor-preview"
        )
    );


    scanCodeBlocks(
        document.querySelector(
            ".editor-preview-side"
        )
    );
}


/* =========================================================
   监听 EasyMDE 预览变化
   ========================================================= */

function observePreview() {

    const previewAreas =
        document.querySelectorAll(
            ".editor-preview, .editor-preview-side"
        );


    previewAreas.forEach(
        function (preview) {

            const observer =
                new MutationObserver(
                    function () {

                        scanCodeBlocks(
                            preview
                        );

                    }
                );


            observer.observe(
                preview,
                {
                    childList: true,
                    subtree: true,
                }
            );

        }
    );
}


/* =========================================================
   页面加载
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    function () {

        initCodeCopy();

        observePreview();

    }
);