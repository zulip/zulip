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

export function scroll_element_into_container($elem, $container, sticky_header_height = 0) {
    // This does the minimum amount of scrolling that is needed to make
    // the element visible.  It doesn't try to center the element, so
    // this will be non-intrusive to users when they already have
    // the element visible.

    $container = ui.get_scroll_element($container);
    const elem_top = $elem.position().top - sticky_header_height;
    const elem_bottom = elem_top + $elem.innerHeight();
    const container_height = $container.height() - sticky_header_height;

    const opts = {
        elem_top,
        elem_bottom,
        container_height,
    };

    const delta = scroll_delta(opts);

    if (delta === 0) {
        return;
    }

    $container.scrollTop($container.scrollTop() + delta);
}
