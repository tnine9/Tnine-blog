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

                        showToast(
                            "昵称保存失败",
                            "error"
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


                    showToast(
                        "网络错误",
                        "error"
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









        /* ==========================================
        点赞成功后就地更新（不刷新页面）
        ========================================== */

        function updateMomentLikeUI(form, result){

            const card =
                form.closest(".moment-card");

            if(!card){
                return;
            }


            const button =
                form.querySelector(
                    "button[type='submit']"
                );


            if(button){

                button.classList.add(
                    "is-liked"
                );


                const label =
                    button.querySelector(
                        ".moment-action-label"
                    );


                if(label){

                    label.textContent =
                        "已赞";

                }


                const countValue =
                    Number(
                        result.like_count || 0
                    );


                let count =
                    button.querySelector(
                        ".moment-action-count"
                    );


                if(countValue > 0){

                    if(!count){

                        count =
                            document.createElement("span");

                        count.className =
                            "moment-action-count";

                        button.appendChild(count);

                    }


                    count.textContent =
                        countValue;

                }else if(count){

                    count.remove();

                }

            }


            /* 赞过行 */
            const likeList =
                card.querySelector(
                    ".moment-like-list"
                );


            if(likeList){

                const likeCountSpan =
                    likeList.querySelector(
                        ".moment-like-count, .like-section-title"
                    );


                if(likeCountSpan){

                    likeCountSpan.textContent =
                        "❤️ " +
                        result.like_count +
                        " 人赞过";

                }

            }


            /* 详情页统计行 */
            const detailLikeCount =
                card.querySelector(
                    ".detail-like-count"
                );


            if(detailLikeCount){

                detailLikeCount.textContent =
                    result.like_count;

            }

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


                            showToast(
                                result.error ||
                                "点赞失败",
                                "error"
                            );


                            return;

                        }



                        /* 就地更新点赞状态，不刷新页面 */

                        updateMomentLikeUI(
                            form,
                            result
                        );



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

        /* ==========================================
        评论成功后就地插入（不刷新页面）
        ========================================== */

        function appendMomentComment(form, result, input){

            const card =
                form.closest(".moment-card");

            if(!card){
                return;
            }


            const list =
                card.querySelector(
                    ".moment-comment-list"
                );


            const newComment =
                document.createElement("div");

            newComment.className =
                "moment-comment";


            const userSpan =
                document.createElement("span");

            userSpan.className =
                "moment-comment-user";

            userSpan.textContent =
                result.nickname;

            newComment.appendChild(userSpan);


            if(result.reply_to_nickname){

                const replySpan =
                    document.createElement("span");

                replySpan.className =
                    "moment-comment-replyto";

                replySpan.textContent =
                    "回复 @" +
                    result.reply_to_nickname;

                newComment.appendChild(replySpan);

            }


            const contentSpan =
                document.createElement("span");

            contentSpan.className =
                "moment-comment-content";

            contentSpan.textContent =
                result.content;

            newComment.appendChild(contentSpan);


            if(list){

                /* 有"查看更多"时插到其之前 */
                const more =
                    list.querySelector(
                        "[data-comment-more]"
                    );

                if(more){

                    list.insertBefore(
                        newComment,
                        more
                    );

                }else{

                    list.appendChild(
                        newComment
                    );

                }

            }else{

                /* 无评论列表则新建 */
                const newList =
                    document.createElement("div");

                newList.className =
                    "moment-comment-list moment-interactive";

                newList.appendChild(newComment);


                const panel =
                    card.querySelector(
                        ".moment-comment-panel"
                    );


                if(panel){

                    card.insertBefore(
                        newList,
                        panel
                    );

                }else{

                    card.appendChild(newList);

                }

            }


            /* 详情页：移除"还没有评论"占位 */
            const empty =
                list?.querySelector(
                    ".moment-comment-empty"
                );

            if(empty){

                empty.remove();

            }


            /* 详情页：更新评论统计 */
            const detailCommentCount =
                card.querySelector(
                    ".detail-comment-count"
                );

            if(detailCommentCount){

                detailCommentCount.textContent =
                    result.comment_count;

            }


            /* 更新评论数 */
            const toggleCount =
                card.querySelector(
                    ".moment-comment-toggle .moment-action-count"
                );

            if(toggleCount){

                toggleCount.textContent =
                    result.comment_count;

            }


            /* 更新"查看全部"按钮 */
            const moreButton =
                card.querySelector(
                    "[data-comment-more]"
                );

            if(moreButton){

                moreButton.dataset.text =
                    "查看全部" +
                    result.comment_count +
                    "条评论";

                moreButton.textContent =
                    "查看全部 " +
                    result.comment_count +
                    " 条评论";

            }


            /* 清空输入框 */
            if(input){

                input.value = "";

            }


            /* 关闭评论面板 */
            const panel =
                card.querySelector(
                    ".moment-comment-panel"
                );

            if(panel){

                panel.classList.remove(
                    "is-open"
                );

            }


            /* 重置详情页回复目标 */
            const replyTarget =
                document.getElementById(
                    "momentReplyTarget"
                );

            if(replyTarget){

                replyTarget.hidden = true;

            }


            const replyToId =
                document.getElementById(
                    "momentReplyToId"
                );

            if(replyToId){

                replyToId.value = "";

            }

        }


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
                                new FormData(form);



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


                            showToast(
                                result.error ||
                                "评论失败",
                                "error"
                            );


                            return;

                        }



                        /* 就地插入评论，不刷新页面 */

                        appendMomentComment(
                            form,
                            result,
                            input
                        );



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
        朋友圈卡片：整卡点击进入详情页
        互动区（点赞/评论/编辑/删除/图片查看）不触发跳转
        ========================================== */

        document
        .querySelectorAll(
            ".moment-card-shell.is-clickable"
        )
        .forEach(
            function(card){

                card.addEventListener(
                    "click",
                    function(event){

                        const url = card.dataset.url;

                        if(!url){
                            return;
                        }

                        const interactive = event.target.closest(
                            ".moment-images, " +
                            ".moment-actions, " +
                            ".moment-admin-actions, " +
                            ".moment-like-list, " +
                            ".moment-comment-list, " +
                            ".moment-comment-panel, " +
                            "a, " +
                            "button, " +
                            "form, " +
                            "input, " +
                            "textarea"
                        );

                        if(interactive){
                            return;
                        }

                        event.preventDefault();

                        window.location.href = url;

                    }
                );

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