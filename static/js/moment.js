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


        /*
        没有弹窗直接结束
        防止其它页面报错
        */

        if (!nicknameModal) {
            return;
        }



        const nicknameInput =
            document.getElementById(
                "nickname-input"
            );


        const nicknameCancel =
            document.getElementById(
                "nickname-cancel"
            );


        const nicknameConfirm =
            document.getElementById(
                "nickname-confirm"
            );



        let pendingAction = null;



        function openNicknameModal(action){

            pendingAction = action;


            nicknameInput.value = "";


            nicknameModal.classList.add(
                "is-open"
            );


            setTimeout(
                ()=>{
                    nicknameInput.focus();
                },
                50
            );

        }




        function closeNicknameModal(){


            nicknameModal.classList.remove(
                "is-open"
            );


            pendingAction = null;

        }




        nicknameCancel?.addEventListener(
            "click",
            closeNicknameModal
        );



        nicknameModal
            .querySelector(
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
                    event.key==="Enter"
                    &&
                    !event.shiftKey
                ){

                    event.preventDefault();


                    nicknameConfirm.click();

                }


            }
        );






        nicknameConfirm?.addEventListener(
            "click",
            async function(){


                const nickname =
                    nicknameInput.value.trim();




                /*
                空昵称
                */

                if(!nickname){


                    const action =
                        pendingAction;


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


                    const formData =
                        new FormData();


                    formData.append(
                        "nickname",
                        nickname
                    );



                    const response =
                        await fetch(
                            "/nickname",
                            {
                                method:"POST",
                                body:formData
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




                    const action =
                        pendingAction;


                    closeNicknameModal();



                    if(action){

                        await action();

                    }



                }catch(error){


                    console.error(error);


                    alert(
                        "网络错误"
                    );

                }



            }
        );








        /*
        ==========================================
        需要昵称操作
        ==========================================
        */


        async function executeWithNickname(action){


            let response =
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


                                    resolve(retry);

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




                        window.location.reload();



                    }
                );


            }
        );









        /*
        ==========================================
        评论展开
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
            button=>{


                button.addEventListener(
                    "click",
                    function(){



                        const list =
                            button.closest(
                                ".moment-comment-list"
                            );



                        const extra =
                            list.querySelector(
                                "[data-comment-extra]"
                            );



                        if(!extra){
                            return;
                        }



                        extra.classList.toggle(
                            "is-expanded"
                        );



                        button.textContent =
                            extra.classList.contains(
                                "is-expanded"
                            )
                            ?
                            "收起评论"
                            :
                            button.dataset.text;



                    }
                );


            }
        );



    }
);