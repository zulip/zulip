import $ from "jquery";

import {buddy_list} from "./buddy_list";
import * as ui from "./ui";

export function scroll_delta(opts) {
    const elem_top = opts.elem_top;
    const container_height = opts.container_height;
    const elem_bottom = opts.elem_bottom;

    let delta = 0;

    if (elem_top < 0) {
        delta = Math.max(elem_top, elem_bottom - container_height);
        delta = Math.min(0, delta);
    } else {
        if (elem_bottom > container_height) {
            delta = Math.min(elem_top, elem_bottom - container_height);
            delta = Math.max(0, delta);
        }
    }

    return delta;
}

export function scroll_element_into_container($elem, $container) {
    // This does the minimum amount of scrolling that is needed to make
    // the element visible.  It doesn't try to center the element, so
    // this will be non-intrusive to users when they already have
    // the element visible.

    $container = ui.get_scroll_element($container);
    const elem_top = $elem.position().top;
    const elem_bottom = elem_top + $elem.innerHeight();

    const opts = {
        elem_top,
        elem_bottom,
        container_height: $container.height(),
    };

    const delta = scroll_delta(opts);

    if (delta === 0) {
        return;
    }

    $container.scrollTop($container.scrollTop() + delta);
}

export function scroll_element_into_container_for_buddy_list($elem, container) {
    container = ui.get_scroll_element(container);
    const elem_top = $elem.offset().top - container.offset().top;
    const elem_bottom = elem_top + $elem.innerHeight();

    const opts = {
        elem_top,
        elem_bottom,
        container_height: container.height(),
    };

    const delta = scroll_delta(opts);

    function do_elements_overlap(rect1, rect2) {
        return !(rect1.top > rect2.bottom);
    }

    if (delta === 0) {
        if ($("#users_heading")[0]) {
            const rect1 = $elem[0].getBoundingClientRect();
            const rect2 = $("#users_heading")[0].getBoundingClientRect();
            if (do_elements_overlap(rect1, rect2)) {
                container.scrollTop(container.scrollTop() - (rect2.bottom - rect1.top));
            }
        }
        if (
            buddy_list.other_keys &&
            buddy_list.other_keys.includes(buddy_list.get_key_from_li({$li: $elem}))
        ) {
            const rect1 = $elem[0].getBoundingClientRect();
            const rect2 = $("#others_heading")[0].getBoundingClientRect();
            if (do_elements_overlap(rect1, rect2)) {
                container.scrollTop(container.scrollTop() - (rect2.bottom - rect1.top));
            }
        }
        return;
    }

    let align_to_top;
    if (delta > 0) {
        align_to_top = false;
    } else {
        align_to_top = true;
    }
    $elem[0].scrollIntoView(align_to_top);

    if ($("#users_heading")[0]) {
        const rect1 = $elem[0].getBoundingClientRect();
        const rect2 = $("#users_heading")[0].getBoundingClientRect();
        if (do_elements_overlap(rect1, rect2)) {
            container.scrollTop(container.scrollTop() - $("#users_heading").innerHeight());
        }
    }
    if (
        buddy_list.other_keys &&
        buddy_list.other_keys.includes(buddy_list.get_key_from_li({$li: $elem}))
    ) {
        const rect1 = $elem[0].getBoundingClientRect();
        const rect2 = $("#others_heading")[0].getBoundingClientRect();
        if (do_elements_overlap(rect1, rect2)) {
            container.scrollTop(container.scrollTop() - $("#others_heading").innerHeight());
        }
    }
}
