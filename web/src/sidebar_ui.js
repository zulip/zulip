import $ from "jquery";

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
