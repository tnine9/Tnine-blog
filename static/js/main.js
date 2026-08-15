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





