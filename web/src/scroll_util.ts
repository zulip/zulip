import $ from "jquery";
import SimpleBar from "simplebar";

import * as util from "./util.ts";

// This type is helpful for testing, where we may have a dummy object instead of an actual jquery object.
type JQueryOrZJQuery = {__zjquery?: true} & JQuery;
type OffsetLike = {top: number};

function has_numeric_length(value: unknown): value is {length: number} {
    return (
        typeof value === "object" &&
        value !== null &&
        typeof Reflect.get(value, "length") === "number"
    );
}

function has_get_bounding_client_rect(
    value: unknown,
): value is {getBoundingClientRect: () => DOMRect} {
    return (
        typeof value === "object" &&
        value !== null &&
        typeof Reflect.get(value, "getBoundingClientRect") === "function"
    );
}

function has_contains(value: unknown): value is {contains: (node: Node) => boolean} {
    return (
        typeof value === "object" &&
        value !== null &&
        typeof Reflect.get(value, "contains") === "function"
    );
}

function has_offset_element(
    value: unknown,
): value is {offset: () => OffsetLike | undefined; innerHeight: () => number | undefined} {
    return (
        typeof value === "object" &&
        value !== null &&
        typeof Reflect.get(value, "offset") === "function" &&
        typeof Reflect.get(value, "innerHeight") === "function"
    );
}

function has_offset_container(value: unknown): value is {
    offset: () => OffsetLike | undefined;
    height: () => number | undefined;
    scrollTop: (arg?: number) => number | JQueryOrZJQuery;
} {
    return (
        typeof value === "object" &&
        value !== null &&
        typeof Reflect.get(value, "offset") === "function" &&
        typeof Reflect.get(value, "height") === "function" &&
        typeof Reflect.get(value, "scrollTop") === "function"
    );
}

export function get_content_element($element: JQuery): JQuery {
    const element = util.the($element);
    const sb = SimpleBar.instances.get(element);
    if (sb) {
        return $(sb.getContentElement()!);
    }
    return $element;
}

export function get_scroll_element($element: JQueryOrZJQuery): JQuery {
    // For testing we just return the element itself.
    if ($element?.__zjquery) {
        return $element;
    }

    const element = util.the($element);
    const sb = SimpleBar.instances.get(element);
    if (sb) {
        return $(sb.getScrollElement()!);
    } else if (element.hasAttribute("data-simplebar")) {
        // The SimpleBar mutation observer hasn’t processed this element yet.
        // Create the SimpleBar early in case we need to add event listeners.
        return $(new SimpleBar(element, {tabIndex: -1}).getScrollElement()!);
    }
    return $element;
}

export function get_left_sidebar_scroll_container(): JQuery {
    return get_scroll_element($("#left_sidebar_scroll_container"));
}

export function reset_scrollbar($element: JQuery): void {
    const element = util.the($element);
    const sb = SimpleBar.instances.get(element);
    if (sb) {
        sb.getScrollElement()!.scrollTop = 0;
    } else {
        element.scrollTop = 0;
    }
}

export function scroll_delta(opts: {
    elem_top: number;
    elem_bottom: number;
    container_height: number;
}): number {
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

export function scroll_element_into_container(
    $elem: JQuery,
    $container: JQuery,
    sticky_header_height = 0,
): void {
    $container = get_scroll_element($container);
    const elem = has_numeric_length($elem) ? util.the($elem) : $elem;
    const container = has_numeric_length($container) ? util.the($container) : $container;

    const can_use_dom_rect =
        has_get_bounding_client_rect(elem) && has_get_bounding_client_rect(container);
    const can_use_offsets = has_offset_element($elem) && has_offset_container($container);

    if (!can_use_dom_rect && can_use_offsets) {
        // Fallback for tests or non-DOM stubs.
        const elem_offset = $elem.offset()?.top ?? 0;
        const container_offset = $container.offset()?.top ?? 0;
        const elem_top = elem_offset - container_offset - sticky_header_height;
        const elem_bottom = elem_top + ($elem.innerHeight() ?? 0);
        const container_height = ($container.height() ?? 0) - sticky_header_height;
        const delta = scroll_delta({
            elem_top,
            elem_bottom,
            container_height,
        });
        if (delta !== 0) {
            $container.scrollTop(($container.scrollTop() ?? 0) + delta);
        }
        return;
    }

    if (!can_use_dom_rect) {
        return;
    }

    const elem_rect = elem.getBoundingClientRect();
    const container_rect = container.getBoundingClientRect();
    const view_top = container_rect.top + sticky_header_height;
    const view_bottom = container_rect.bottom;
    const selection = window.getSelection();
    let caret_rect = null;

    if (selection && selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        const anchor_node = selection.anchorNode;
        const caret_in_container =
            anchor_node && has_contains(container) && container.contains(anchor_node);
        if (caret_in_container) {
            caret_rect = range.getBoundingClientRect();
        }
    }

    let delta = 0;
    const PADDING = 30;
    const view_height = view_bottom - view_top;
    const is_tall_element = elem_rect.height > view_height;
    if (caret_rect && caret_rect.height > 0) {
        if (caret_rect.top < view_top) {
            delta = caret_rect.top - view_top - PADDING;
        } else if (caret_rect.bottom > view_bottom) {
            delta = caret_rect.bottom - view_bottom + PADDING;
        }
    }
    if (delta === 0) {
        if (is_tall_element) {
            delta = elem_rect.top - view_top - PADDING;
        } else if (elem_rect.top < view_top) {
            delta = elem_rect.top - view_top - PADDING;
        } else if (elem_rect.bottom > view_bottom) {
            delta = elem_rect.bottom - view_bottom + PADDING;
        }
    }
    if (Math.abs(delta) < 2) {
        return;
    }

    const prefers_reduced_motion =
        window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const behavior: ScrollBehavior = prefers_reduced_motion ? "auto" : "smooth";
    container.scrollBy({
        top: delta,
        behavior,
    });
}
