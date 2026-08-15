document.addEventListener(
    "DOMContentLoaded",
    function () {


        /*
        ==========================================
        昵称弹窗
        ==========================================
        */

        const nicknameModal =
            document.getElementById(
                "nickname-modal"
            );


        let pendingAction = null;


        function openNicknameModal(action){

            if(!nicknameModal){
                return;
            }


            pendingAction = action;


            const input =
                document.getElementById(
                    "nickname-input"
                );


            if(input){

                input.value = "";

            }


            nicknameModal.classList.add(
                "is-open"
            );


            setTimeout(
                ()=>{

                    input?.focus();

                },
                50
            );

        }



        function closeNicknameModal(){

            if(!nicknameModal){
                return;
            }


            nicknameModal.classList.remove(
                "is-open"
            );


            pendingAction = null;

        }




        const nicknameCancel =
            document.getElementById(
                "nickname-cancel"
            );


        const nicknameConfirm =
            document.getElementById(
                "nickname-confirm"
            );


        const nicknameInput =
            document.getElementById(
                "nickname-input"
            );



        nicknameCancel?.addEventListener(
            "click",
            closeNicknameModal
        );



        nicknameModal
        ?.querySelector(
            ".nickname-modal-backdrop"
        )
        ?.addEventListener(
            "click",
            closeNicknameModal
        );



        nicknameInput?.addEventListener(
            "keydown",
            function(event){

                if(
                    event.key === "Enter"
                    &&
                    !event.shiftKey
                ){

                    event.preventDefault();

                    nicknameConfirm?.click();

                }

            }
        );





        nicknameConfirm?.addEventListener(
            "click",
            async function(){


                const nickname =
                    nicknameInput.value.trim();



                const action =
                    pendingAction;



                /*
                匿名
                */

                if(!nickname){

                    closeNicknameModal();


                    if(action){

                        await action(
                            "匿名访客"
                        );

                    }


                    return;

                }





                /*
                保存昵称
                */

                try{


                    const data =
                        new FormData();


                    data.append(
                        "nickname",
                        nickname
                    );



                    const response =
                        await fetch(
                            "/nickname",
                            {
                                method:"POST",
                                body:data
                            }
                        );



                    const result =
                        await response.json();



                    if(!result.success){

                        alert(
                            "昵称保存失败"
                        );

                        return;

                    }




                    closeNicknameModal();



                    if(action){

                        await action();

                    }



                }
                catch(error){

                    console.error(
                        error
                    );


                    alert(
                        "网络错误"
                    );

                }



            }
        );







        /*
        ==========================================
        需要昵称执行
        ==========================================
        */


        async function executeWithNickname(action){


            const response =
                await action();



            if(
                response.status === 401
            ){


                const result =
                    await response.json();



                if(
                    result.nickname_required
                ){


                    return new Promise(
                        resolve=>{


                            openNicknameModal(
                                async function(nickname){


                                    const retry =
                                        await action(
                                            nickname
                                        );


                                    resolve(
                                        retry
                                    );


                                }
                            );


                        }
                    );

                }


            }



            return response;


        }









        /*
        ==========================================
        点赞
        ==========================================
        */


        document
        .querySelectorAll(
            ".moment-like-form"
        )
        .forEach(
            function(form){


                form.addEventListener(
                    "submit",
                    async function(event){


                        event.preventDefault();



                        async function action(
                            nickname=null
                        ){


                            const data =
                                new FormData();



                            if(nickname){

                                data.append(
                                    "nickname",
                                    nickname
                                );

                            }



                            return fetch(
                                form.action,
                                {
                                    method:"POST",
                                    body:data
                                }
                            );


                        }





                        const response =
                            await executeWithNickname(
                                action
                            );



                        if(!response){

                            return;

                        }



                        const result =
                            await response.json();




                        if(!result.success){


                            alert(
                                result.error ||
                                "点赞失败"
                            );


                            return;

                        }



                        /*
                        刷新同步状态
                        */

                        window.location.reload();



                    }
                );


            }
        );









/*
==========================================
评论输入框展开
==========================================
*/
document
.querySelectorAll(
    ".moment-comment-toggle"
)
.forEach(
    function(button){

        button.addEventListener(
            "click",
            function(){

                const target =
                    document.getElementById(
                        button.dataset.commentTarget
                    );

                if(!target){
                    return;
                }

                target.classList.toggle(
                    "is-open"
                );

            }
        );

    }
);

        /*
        ==========================================
        提交评论
        ==========================================
        */


        document
        .querySelectorAll(
            ".moment-comment-form"
        )
        .forEach(
            function(form){


                form.addEventListener(
                    "submit",
                    async function(event){


                        event.preventDefault();



                        const input =
                            form.querySelector(
                                ".moment-comment-input"
                            );



                        const content =
                            input.value.trim();



                        if(!content){

                            return;

                        }




                        async function action(
                            nickname=null
                        ){


                            const data =
                                new FormData();



                            data.append(
                                "content",
                                content
                            );



                            if(nickname){

                                data.append(
                                    "nickname",
                                    nickname
                                );

                            }




                            return fetch(
                                form.action,
                                {
                                    method:"POST",
                                    body:data
                                }
                            );


                        }




                        const response =
                            await executeWithNickname(
                                action
                            );



                        const result =
                            await response.json();




                        if(!result.success){


                            alert(
                                result.error ||
                                "评论失败"
                            );


                            return;

                        }



                        window.location.reload();



                    }
                );


            }
        );









        /*
        ==========================================
        展开更多评论
        ==========================================
        */

document
.querySelectorAll(
    "[data-comment-more]"
)
.forEach(
    function(button){


        button.addEventListener(
            "click",
            function(){


                const list =
                    button.closest(
                        ".moment-comment-list"
                    );


                if(!list){
                    return;
                }



                const extra =
                    list.querySelector(
                        "[data-comment-extra]"
                    );



                if(!extra){
                    return;
                }



                const isExpanded =
                    extra.classList.toggle(
                        "is-expanded"
                    );



                if(isExpanded){

                    button.innerText =
                        "收起评论";


                }else{


                    button.innerText =
                        button.dataset.text;


                }



            }
        );


    }
);



    }
);