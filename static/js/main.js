/* =========================================================
   Tnine 全局 JS
   ========================================================= */



document.addEventListener(
    "DOMContentLoaded",
    () => {


        // 昵称弹窗 / 评论展开 / 评论更多 统一由 moment.js 管理，
        // 此处不重复绑定，避免同一元素事件被触发两次
        initCardNavigation();


        initUserMenu();


        initThemeToggle();


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

/*
=========================================================
明暗主题切换
按钮图标由 CSS 根据 html[data-theme] 自动显隐，
JS 只负责切换主题并持久化到 localStorage
=========================================================
*/


function initThemeToggle(){


    const toggle =
        document.getElementById(
            "themeToggle"
        );


    if(
        !toggle
    ){

        return;

    }




    toggle.addEventListener(
        "click",
        function(){


            const root =
                document.documentElement;


            const next =
                root.getAttribute(
                    "data-theme"
                ) === "dark"
                    ? "light"
                    : "dark";


            root.setAttribute(
                "data-theme",
                next
            );


            try {

                localStorage.setItem(
                    "tnine-theme",
                    next
                );

            } catch (e) { }


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