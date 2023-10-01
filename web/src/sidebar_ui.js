import $ from "jquery";

import {media_breakpoints_num} from "./css_variables";
import * as popovers from "./popovers";
import * as resize from "./resize";
import * as spectators from "./spectators";

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

export function initialize() {
    $("body").on("click", ".login_button", (e) => {
        e.preventDefault();
        e.stopPropagation();
        window.location.href = spectators.build_login_link();
    });

    $("#userlist-toggle-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const sidebarHidden = !$(".app-main .column-right").hasClass("expanded");
        popovers.hide_all();
        if (sidebarHidden) {
            show_userlist_sidebar();
        }
    });

    $("#streamlist-toggle-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const sidebarHidden = !$(".app-main .column-left").hasClass("expanded");
        popovers.hide_all();
        if (sidebarHidden) {
            show_streamlist_sidebar();
        }
    });
}
