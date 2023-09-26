import $ from "jquery";

import * as resize from "./resize";

export function hide_userlist_sidebar() {
    $(".app-main .column-right").removeClass("expanded");
}

export function show_userlist_sidebar() {
    $(".app-main .column-right").addClass("expanded");
    resize.resize_page_components();
}
