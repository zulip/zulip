"use strict";

/* For the making the left sidebar resizable */
const columnMiddle = $(".column-middle");
const leftSidebar = $("#left-sidebar");
const composeContent = $(".compose-content");
const recipientBarMain = $(".recipient-bar-main");
const floatingRecipientBar = $("#floating_recipient_bar");

function leftSidebarResize(event) {
    /*

    This function resizes the sidebar and at the same time managing the other items
        it increases the width of the left sidebar according to the mouse event,
        Changes the margin-left of the column-middle class elements
        Also changes the margin left of the compose box

    */

    leftSidebar.css("width", event.pageX - leftSidebar.offset().left - 8 + "px");
    columnMiddle.css("margin-left", event.pageX - leftSidebar.offset().left + "px");
    recipientBarMain.css(
        "padding-left",
        -Number.parseInt(floatingRecipientBar.css("left"), 10) + "px",
    );
    composeContent.css("margin-left", event.pageX - leftSidebar.offset().left + "px");
}

function stopResize() {
    window.removeEventListener("mousemove", leftSidebarResize);
}

$("#left-sidebar-resizer").on("mousedown", (event) => {
    event.preventDefault();
    window.addEventListener("mousemove", leftSidebarResize);
    window.addEventListener("mouseup", stopResize);
});
