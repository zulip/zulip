$(function () {
    $("#stream-filters-container").perfectScrollbar({
        suppressScrollX: true,
        useKeyboard: false,
        wheelSpeed: 20,
    });
});

function scrollbarWidth() {
    $('body').prepend('<div id="outertest" style="width:200px; height:150px; position: absolute; top: 0; left: 0; overflow-x:hidden; overflow-y:scroll; background: #ff0000; visibility: hidden;"><div id="innertest" style="width:100%; height: 200px; overflow-y: visible;">&nbsp;</div></div>');

    var scrollwidth = $("#outertest").outerWidth() - $("#innertest").outerWidth();

    $("#outertest").remove();

    return scrollwidth;
}

// Workaround for browsers with fixed scrollbars
$(function () {


   var sbWidth = scrollbarWidth();

   if (sbWidth > 0) {

    $(".header").css("left", "-" + sbWidth + "px");
    $(".header-main").css("left", sbWidth + "px");
    $(".header-main").css("max-width", (1400 + sbWidth) + "px");
    $(".header-main .column-middle").css("margin-right", (250 + sbWidth) + "px");

    $(".fixed-app").css("left", "-" + sbWidth + "px");
    $(".fixed-app .app-main").css("max-width", (1400 + sbWidth) + "px");
    $(".fixed-app .column-middle").css("margin-left", (250 + sbWidth) + "px");

    $(".column-right").css("right", sbWidth + "px");
    $(".app-main .right-sidebar").css({"margin-left": (sbWidth) + "px",
                                       width: (250 - sbWidth) + "px"});

    $("#compose").css("left", "-" + sbWidth + "px");
    $(".compose-content").css({left: sbWidth + "px",
                               "margin-right": (250 + sbWidth) + "px"});
    $("#compose-container").css("max-width", (1400 + sbWidth) + "px");

    $("head").append("<style> @media (max-width: 975px) { .compose-content, .header-main .column-middle { margin-right: " + (7 + sbWidth) + "px !important; } } " +
                     "@media (max-width: 775px) { .fixed-app .column-middle { margin-left: " + (7 + sbWidth) + "px !important; } } " +
                     "</style>");
   }

});
