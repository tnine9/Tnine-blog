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


        initAdminThemePanel();


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
后台：切换主题面板
- 仅管理员可见/可操作（按钮在后台页面）
- 点击"切换主题"按钮展开所有主题选项
- 点击选项后提交到 /admin/theme，成功后全站生效
=========================================================
*/


function initAdminThemePanel(){


    const button =
        document.getElementById(
            "adminThemeButton"
        );


    const panel =
        document.getElementById(
            "adminThemePanel"
        );


    if(
        !button
        || !panel
    ){

        return;

    }


    /* 展开 / 收起 */

    button.addEventListener(
        "click",
        function(e){

            e.stopPropagation();

            panel.classList.toggle(
                "is-open"
            );

        }
    );


    /* 点击面板外收起 */

    document.addEventListener(
        "click",
        function(e){

            if (
                !panel.contains(e.target)
                && !button.contains(e.target)
            ) {

                panel.classList.remove(
                    "is-open"
                );

            }

        }
    );


    /* 点击主题选项：提交并全局切换 */

    const options =
        panel.querySelectorAll(
            ".theme-option"
        );


    options.forEach(
        function(option){

            option.addEventListener(
                "click",
                function(){

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


                                panel.classList.remove(
                                    "is-open"
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