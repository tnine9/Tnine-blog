/* =========================================================
   Tnine 全局 JS
   ========================================================= */



document.addEventListener(
    "DOMContentLoaded",
    () => {


        initNicknameModal();


        initCommentToggle();


        initCommentMore();


        initCardNavigation();


        initUserMenu();


    }
);





/*
=========================================================
昵称弹窗
=========================================================
*/


function initNicknameModal(){


    const modal =
        document.querySelector(
            ".nickname-modal"
        );


    if(!modal){

        return;

    }




    const openButtons =
        document.querySelectorAll(
            "[data-open-nickname]"
        );



    const closeButtons =
        modal.querySelectorAll(
            "[data-close-modal]"
        );





    function openModal(){


        modal.classList.add(
            "is-open"
        );


        document.body.style.overflow =
            "hidden";


    }






    function closeModal(){


        modal.classList.remove(
            "is-open"
        );


        document.body.style.overflow =
            "";


    }







    openButtons.forEach(
        btn=>{


            btn.addEventListener(
                "click",
                openModal
            );


        }
    );






    closeButtons.forEach(
        btn=>{


            btn.addEventListener(
                "click",
                closeModal
            );


        }
    );








    modal.addEventListener(
        "click",
        e=>{


            if(
                e.target.classList.contains(
                    "nickname-modal-backdrop"
                )
            ){


                closeModal();


            }


        }
    );



}









/*
=========================================================
评论展开
=========================================================
*/


function initCommentToggle(){


    const buttons =
        document.querySelectorAll(
            ".moment-comment-toggle"
        );



    buttons.forEach(
        button=>{


            button.addEventListener(
                "click",
                ()=>{


                    const targetId =
                        button.dataset.commentTarget;



                    const panel =
                        document.getElementById(
                            targetId
                        );



                    if(!panel){

                        return;

                    }




                    panel.classList.toggle(
                        "is-open"
                    );



                }
            );



        }
    );



}









/*
=========================================================
查看更多评论
=========================================================
*/


function initCommentMore(){


    const buttons =
        document.querySelectorAll(
            "[data-comment-more]"
        );



    buttons.forEach(
        button=>{


            button.addEventListener(
                "click",
                ()=>{


                    const box =
                        button
                        .previousElementSibling;



                    if(!box){

                        return;

                    }




                    box.classList.toggle(
                        "show-all"
                    );



                    if(
                        box.classList.contains(
                            "show-all"
                        )
                    ){

                        button.innerText =
                            "收起评论";


                    }
                    else{


                        button.innerText =
                            button.dataset.text;



                    }



                }
            );


        }
    );


}









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
用户头像菜单
=========================================================
*/


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