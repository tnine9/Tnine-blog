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


        /* ==========================================
        暴露给其它页面内联脚本使用：
        - article_detail.html 文章点赞/评论
        - messages.html 留言发布
        - message_detail.html 留言回复
        这些函数在 DOMContentLoaded 闭包内定义，
        必须挂到 window 才能被其它回调访问。
        ========================================== */

        window.executeWithNickname =
            executeWithNickname;

        window.openNicknameModal =
            openNicknameModal;


    }
);



    }
);


/*
==========================================
朋友圈图片查看器
==========================================
*/



let viewerImages = [];

let viewerIndex = 0;



function openImageViewer(images,index){


    viewerImages = images;

    viewerIndex = index;



    const viewer =
        document.getElementById(
            "image-viewer"
        );


    const img =
        document.getElementById(
            "viewer-image"
        );



    if(!viewer || !img){

        console.log(
            "图片查看器不存在"
        );

        return;

    }



    img.src =
        viewerImages[
            viewerIndex
        ];



    viewer.classList.add(
        "show"
    );


}






function closeImageViewer(){


    const viewer =
        document.getElementById(
            "image-viewer"
        );


    if(viewer){

        viewer.classList.remove(
            "show"
        );

    }


}





document.addEventListener(
"click",
function(event){


    const viewer =
        document.getElementById(
            "image-viewer"
        );



    if(
        viewer &&
        event.target === viewer
    ){

        closeImageViewer();

    }


});



function showNextImage(){


    if(
        viewerImages.length <= 1
    ){

        return;

    }



    viewerIndex++;



    if(
        viewerIndex >= viewerImages.length
    ){

        viewerIndex = 0;

    }



    document
    .getElementById(
        "viewer-image"
    )
    .src =
    viewerImages[
        viewerIndex
    ];

}




function showPrevImage(){


    if(
        viewerImages.length <= 1
    ){

        return;

    }



    viewerIndex--;



    if(
        viewerIndex < 0
    ){

        viewerIndex =
            viewerImages.length - 1;

    }



    document
    .getElementById(
        "viewer-image"
    )
    .src =
    viewerImages[
        viewerIndex
    ];

}







document
.querySelectorAll(
".moment-image-item"
)
.forEach(
function(item){


const img =
item.querySelector(
"img"
);



img.addEventListener(
"click",
function(){


const images =
JSON.parse(
item.dataset.images
);



const index =
Number(
item.dataset.imageIndex
);



openImageViewer(
images,
index
);


});


});