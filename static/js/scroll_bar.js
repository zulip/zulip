import $ from "jquery";

import {media_breakpoints} from "./css_variables";
import {user_settings} from "./user_settings";

// A few of our width properties in Zulip depend on the width of the
// browser scrollbar that is generated at the far right side of the
// page, which unfortunately varies depending on the browser and
// cannot be detected directly using CSS.  As a result, we adjust a
// number of element widths based on the value detected here.
//
// From https://stackoverflow.com/questions/13382516/getting-scroll-bar-width-using-javascript
function getScrollbarWidth() {
    const outer = document.createElement("div");
    outer.style.visibility = "hidden";
    outer.style.width = "100px";
    outer.style.msOverflowStyle = "scrollbar"; // needed for WinJS apps

    document.body.append(outer);

    const widthNoScroll = outer.offsetWidth;
    // force scrollbars
    outer.style.overflow = "scroll";

    // add innerdiv
    const inner = document.createElement("div");
    inner.style.width = "100%";
    outer.append(inner);

    const widthWithScroll = inner.offsetWidth;

    // remove divs
    outer.remove();

    return widthNoScroll - widthWithScroll;
}

let sbWidth;

export function initialize() {
    // Workaround for browsers with fixed scrollbars
    sbWidth = getScrollbarWidth();
    // These need to agree with zulip.css
    const left_sidebar_width = 270;
    const right_sidebar_width = 250;

    if (sbWidth > 0) {
        $(".header").css("left", "-" + sbWidth + "px");
        $(".header-main").css("left", sbWidth + "px");
        $(".header-main .column-middle").css("margin-right", 7 + sbWidth + "px");

        $(".fixed-app").css("left", "-" + sbWidth + "px");
        $(".fixed-app .column-middle").css("margin-left", 7 + sbWidth + "px");

        $(".column-right").css("right", sbWidth + "px");
        $(".app-main .right-sidebar").css({
            "margin-left": sbWidth + "px",
            width: right_sidebar_width - sbWidth + "px",
        });

        $("#compose").css("left", "-" + sbWidth + "px");
        $("#compose-content").css({left: sbWidth + "px", "margin-right": 7 + sbWidth + "px"});
        $("#keyboard-icon").css({"margin-right": sbWidth + "px"});

        $("head").append(
            "<style> @media (min-width: " +
                media_breakpoints.xl_min +
                ") { #compose-content, .header-main .column-middle { margin-right: " +
                (right_sidebar_width + sbWidth) +
                "px !important; } } " +
                "@media (min-width: " +
                media_breakpoints.md_min +
                ") { .fixed-app .column-middle { margin-left: " +
                (left_sidebar_width + sbWidth) +
                "px !important; } } " +
                "</style>",
        );
    }
    set_layout_width();
}

export function set_layout_width() {
    // This logic unfortunately leads to a flash of mispositioned
    // content when reloading a Zulip browser window.  More details
    // are available in the comments on the max-width of 1400px in
    // the .app-main CSS rules.
    if (user_settings.fluid_layout_width) {
        $(".header-main").css("max-width", "inherit");
        $(".app .app-main").css("max-width", "inherit");
        $(".fixed-app .app-main").css("max-width", "inherit");
        $("#compose-container").css("max-width", "inherit");
    } else {
        $(".header-main").css("max-width", 1400 + sbWidth + "px");
        $(".app .app-main").css("max-width", 1400 + "px");
        $(".fixed-app .app-main").css("max-width", 1400 + sbWidth + "px");
        $("#compose-container").css("max-width", 1400 + sbWidth + "px");
    }
}
