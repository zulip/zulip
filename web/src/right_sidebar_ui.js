import $ from "jquery";

import * as resize from "./resize";

export function hide_userlist_sidebar() {
    $(".app-main .column-right").removeClass("expanded");
}

export function show_userlist_sidebar() {
    $(".app-main .column-right").addClass("expanded");
    resize.resize_page_components();
}

export function register_click_handlers() {
    document.addEventListener(
        "click",
        (e) => {
            const $right_column = $(".app-main .column-right");
            const sidebarHidden = !$right_column.hasClass("expanded");
            const $elt = $(e.target);
            const toggle_button_clicked = Boolean($elt.closest("#userlist-toggle-button").length);
            const click_outside_right_sidebar = !$elt.closest($right_column).length;
            if (!sidebarHidden && (click_outside_right_sidebar || toggle_button_clicked)) {
                hide_userlist_sidebar();
            }

            if (sidebarHidden && toggle_button_clicked) {
                show_userlist_sidebar();
            }
        },
        {capture: true},
    );
}
