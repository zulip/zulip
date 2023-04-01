import $ from "jquery";

import {user_settings} from "./user_settings";

// A few of our width properties in Zulip depend on the width of the
// browser scrollbar that is generated at the far right side of the
// page, which unfortunately varies depending on the browser and
// cannot be detected directly using CSS.  As a result, we adjust a
// number of element widths based on the value detected here.
//
// From https://stackoverflow.com/questions/13382516/getting-scroll-bar-width-using-javascript
function getScrollbarWidth(): number {
    const outer = document.createElement("div");
    outer.style.visibility = "hidden";
    outer.style.width = "100px";

    document.body.append(outer);

    const widthNoScroll = outer.offsetWidth;
    // force scrollbars
    outer.style.overflow = "scroll";

    // add inner div
    const inner = document.createElement("div");
    inner.style.width = "100%";
    outer.append(inner);

    const widthWithScroll = inner.offsetWidth;

    // remove divs
    outer.remove();

    return widthNoScroll - widthWithScroll;
}

export function set_layout_width(): void {
    if (user_settings.fluid_layout_width) {
        $(".header-main, .app .app-main, #compose-container").css("max-width", "inherit");
    } else {
        $(".header-main, .app .app-main, #compose-container").css("max-width", "1400px");
    }
}

let sbWidth: number;

export function initialize(): void {
    // Workaround for browsers with fixed scrollbars
    sbWidth = getScrollbarWidth();
    if (sbWidth > 0) {
        // Reduce width of screen-wide parent containers, whose width doesn't vary with scrollbar width, by scrollbar width.
        $("#navbar-container .header, #compose").css("width", `calc(100% - ${sbWidth}px)`);
    }
    set_layout_width();
}
