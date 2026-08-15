/* =========================================================
   Tnine 全局 JS
   ========================================================= */


document.addEventListener(
    "DOMContentLoaded",
    () => {


        initNicknameModal();


        initCommentToggle();


        initCommentMore();


    }
);





/*
    昵称弹窗
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
    评论输入框展开
*/


function initCommentToggle(){


    document
    .querySelectorAll(
        ".moment-comment-toggle"
    )
    .forEach(
        button=>{


            button.addEventListener(
                "click",
                ()=>{


                    const panel =
                        button
                        .closest(
                            ".moment-card"
                        )
                        .querySelector(
                            ".moment-comment-panel"
                        );


                    if(panel){

                        panel.classList.toggle(
                            "is-open"
                        );

                    }


                }
            );


        }
    );

}





/*
    展开更多评论
*/


function initCommentMore(){


    document
    .querySelectorAll(
        ".moment-comments-more"
    )
    .forEach(
        button=>{


            button.addEventListener(
                "click",
                ()=>{


                    const extra =
                        button
                        .parentElement
                        .querySelectorAll(
                            ".moment-comment-extra"
                        );


                    extra.forEach(
                        item=>{


                            item.classList.toggle(
                                "is-expanded"
                            );


                        }
                    );



                    button.textContent =
                        button.textContent.includes(
                            "更多"
                        )
                        ?
                        "查看更多评论"
                        :
                        "";


                }
            );


        }
    );


}