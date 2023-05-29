import $ from "jquery";

import {user_settings} from "./user_settings";

export function set_layout_width(): void {
    if (user_settings.fluid_layout_width) {
        $("body").addClass("fluid_layout_width");
    } else {
        $("body").removeClass("fluid_layout_width");
    }
}

export function handle_overlay_scrollbars(): void {
    // If right sidebar scrollbar overlaps with browser scrollbar, move the right
    // sidebar scrollbar to the left. Done on fluid screen width and when scrollbars overlap.
    const scrollbar_width = window.innerWidth - document.documentElement.clientWidth;
    if (scrollbar_width === 0) {
        const max_app_width = 1400;
        const max_scrollbar_width = 20;
        const are_scrollbars_overlapping = window.innerWidth < max_app_width + max_scrollbar_width;
        if (user_settings.fluid_layout_width || are_scrollbars_overlapping) {
            $("body").addClass("has-overlay-scrollbar");
            return;
        }
    }

    $("body").removeClass("has-overlay-scrollbar");
}

export function initialize(): void {
    set_layout_width();
    handle_overlay_scrollbars();
    const middle_column = $(".app .column-middle").expectOne()[0];
    const resize_observer = new ResizeObserver(handle_overlay_scrollbars);
    resize_observer.observe(middle_column);
}
