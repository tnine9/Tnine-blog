/* =========================================================
   Tnine 全局 JS
   ========================================================= */

/* ---------- 轻量 Toast（全局反馈，供 moment.js 等调用） ---------- */

window.showToast = function (message, type) {

    type = type || "info";

    var container = document.getElementById("tnine-toast-container");

    if (!container) {
        container = document.createElement("div");
        container.id = "tnine-toast-container";
        container.className = "tnine-toast-container";
        document.body.appendChild(container);
    }

    var item = document.createElement("div");
    item.className = "tnine-toast-item tnine-toast-" + type;
    item.textContent = message;
    container.appendChild(item);

    setTimeout(function () {
        item.classList.add("is-hide");
        setTimeout(function () {
            item.remove();
        }, 300);
    }, 2600);

};



document.addEventListener(
    "DOMContentLoaded",
    () => {


        // 昵称弹窗 / 评论展开 / 评论更多 统一由 moment.js 管理，
        // 此处不重复绑定，避免同一元素事件被触发两次
        initCardNavigation();


        initUserMenu();


        initHomeThemeDropdown();


    }
);





/*
=========================================================
内容卡片跳转
点击空白区域进入详情
=========================================================
*/


function initCardNavigation(){


    const cards =
        document.querySelectorAll(
            ".content-card"
        );



    cards.forEach(
        card=>{


            card.addEventListener(
                "click",
                function(e){



                    /*
                    点击互动区域不跳转
                    */

                    if(
                        e.target.closest(
                            ".moment-interactive"
                        )
                    ){

                        return;

                    }




                    /*
                    点击已有功能元素不跳转
                    */

                    if(
                        e.target.closest(
                            "a,button,input,textarea,img"
                        )
                    ){

                        return;

                    }





                    /*
                    只有点击卡片空白区域才跳转
                    */


                    const url =
                        this.dataset.url;



                    if(url){


                        window.location.href =
                            url;


                    }


                }
            );


        }
    );


}


/* =========================================================
   用户头像菜单
   ========================================================= */


function initUserMenu(){


    const button =
        document.getElementById(
            "userMenuButton"
        );


    const dropdown =
        document.getElementById(
            "userDropdown"
        );



    if(
        !button ||
        !dropdown
    ){

        return;

    }




    button.addEventListener(
        "click",
        function(e){


            e.stopPropagation();


            dropdown.classList.toggle(
                "is-open"
            );


        }
    );






    document.addEventListener(
        "click",
        function(){


            dropdown.classList.remove(
                "is-open"
            );


        }
    );






    dropdown.addEventListener(
        "click",
        function(e){


            e.stopPropagation();


        }
    );



}


/* =========================================================
   控制台首页：网站设置卡片内切换主题下拉
- 点击"切换主题"展开下拉（浅色 / 深色）
- 点击选项提交到 /admin/theme，成功后全站生效
========================================================= */


function initHomeThemeDropdown(){


    const wraps =
        document.querySelectorAll(
            ".home-theme-wrap"
        );


    if (
        !wraps.length
    ) {

        return;

    }


    wraps.forEach(
        function(wrap){

            const trigger =
                wrap.querySelector(
                    ".home-theme-trigger"
                );

            const dropdown =
                wrap.querySelector(
                    ".home-theme-dropdown"
                );

            if (
                !trigger
                || !dropdown
            ) {

                return;

            }


            /* 展开 / 收起 */

            trigger.addEventListener(
                "click",
                function(e){

                    e.preventDefault();
                    e.stopPropagation();

                    dropdown.classList.toggle(
                        "is-open"
                    );

                    trigger.setAttribute(
                        "aria-expanded",
                        dropdown.classList.contains(
                            "is-open"
                        )
                    );

                }
            );


            /* 点击面板外收起 */

            document.addEventListener(
                "click",
                function(e){

                    if (
                        !dropdown.contains(e.target)
                        && !trigger.contains(e.target)
                    ) {

                        dropdown.classList.remove(
                            "is-open"
                        );

                        trigger.setAttribute(
                            "aria-expanded",
                            "false"
                        );

                    }

                }
            );


            /* 点击选项：提交并全局切换 */

            const options =
                dropdown.querySelectorAll(
                    ".home-theme-option"
                );


            options.forEach(
                function(option){

                    option.addEventListener(
                        "click",
                        function(e){

                            e.preventDefault();
                            e.stopPropagation();

                            const theme =
                                option.getAttribute(
                                    "data-theme"
                                );

                            if (!theme) {

                                return;

                            }

                            const form =
                                new FormData();

                            form.append(
                                "theme",
                                theme
                            );

                            fetch(
                                "/admin/theme",
                                {
                                    method: "POST",
                                    body: form,
                                    headers: {
                                        "X-Requested-With": "XMLHttpRequest"
                                    }
                                }
                            )
                            .then(
                                function(res){

                                    return res.json();

                                }
                            )
                            .then(
                                function(data){

                                    if (
                                        data
                                        && data.ok
                                    ) {

                                        document.documentElement.setAttribute(
                                            "data-theme",
                                            data.theme
                                        );

                                        /* 更新选中态 */

                                        options.forEach(
                                            function(opt){

                                                opt.classList.toggle(
                                                    "is-selected",
                                                    opt.getAttribute(
                                                        "data-theme"
                                                    ) === data.theme
                                                );

                                            }
                                        );

                                        dropdown.classList.remove(
                                            "is-open"
                                        );

                                        trigger.setAttribute(
                                            "aria-expanded",
                                            "false"
                                        );

                                    }

                                }
                            )
                            .catch(
                                function(){ }
                            );

                        }
                    );

                }
            );

        }
    );


}
