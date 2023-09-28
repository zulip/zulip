import $ from "jquery";

import {media_breakpoints_num} from "./css_variables";
import * as resize from "./resize";

export function hide_userlist_sidebar() {
    $(".app-main .column-right").removeClass("expanded");
}

export function show_userlist_sidebar() {
    $(".app-main .column-right").addClass("expanded");
    resize.resize_page_components();
}

export function show_streamlist_sidebar() {
    $(".app-main .column-left").addClass("expanded");
    resize.resize_stream_filters_container();
}

export function hide_streamlist_sidebar() {
    $(".app-main .column-left").removeClass("expanded");
}

export function any_sidebar_expanded_as_overlay() {
    if (window.innerWidth > media_breakpoints_num.xl) {
        // Sidebars are always visible beyond xl breakpoint.
        return false;
    }
    return Boolean($("[class^='column-'].expanded").length);
}
