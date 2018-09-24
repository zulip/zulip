
var scroll_bar = (function () {

var exports = {};

// From https://stackoverflow.com/questions/13382516/getting-scroll-bar-width-using-javascript
function getScrollbarWidth() {
    var outer = document.createElement("div");
    outer.style.visibility = "hidden";
    outer.style.width = "100px";
    outer.style.msOverflowStyle = "scrollbar"; // needed for WinJS apps

    document.body.appendChild(outer);

    var widthNoScroll = outer.offsetWidth;
    // force scrollbars
    outer.style.overflow = "scroll";

    // add innerdiv
    var inner = document.createElement("div");
    inner.style.width = "100%";
    outer.appendChild(inner);

    var widthWithScroll = inner.offsetWidth;

    // remove divs
    outer.parentNode.removeChild(outer);

    return widthNoScroll - widthWithScroll;
}

exports.initialize = function () {
// Workaround for browsers with fixed scrollbars
    var sbWidth = getScrollbarWidth();

    if (sbWidth > 0) {
        $(".header").css("left", "-" + sbWidth + "px");
        $(".header-main").css("left", sbWidth + "px");
        $(".header-main").css("max-width", 1400 + sbWidth + "px");
        $(".header-main .column-middle").css("margin-right", 250 + sbWidth + "px");

        $(".fixed-app").css("left", "-" + sbWidth + "px");
        $(".fixed-app .app-main").css("max-width", 1400 + sbWidth + "px");
        $(".fixed-app .column-middle").css("margin-left", 250 + sbWidth + "px");

        $(".column-right").css("right", sbWidth + "px");
        $(".app-main .right-sidebar").css({"margin-left": sbWidth + "px",
                                           width: 250 - sbWidth + "px"});

        $("#compose").css("left", "-" + sbWidth + "px");
        $(".compose-content").css({left: sbWidth + "px",
                                   "margin-right": 250 + sbWidth + "px"});
        $("#compose-container").css("max-width", 1400 + sbWidth + "px");
        $('#keyboard-icon').css({right: sbWidth + 13 + "px"});

        $("head").append("<style> @media (max-width: 1165px) { .compose-content, .header-main .column-middle { margin-right: " + (7 + sbWidth) + "px !important; } } " +
                         "@media (max-width: 775px) { .fixed-app .column-middle { margin-left: " + (7 + sbWidth) + "px !important; } } " +
                         "</style>");
    }

    ui.set_up_scrollbar($("#stream-filters-container"));
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = scroll_bar;
}

window.scroll_bar = scroll_bar;
