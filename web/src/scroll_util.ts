import $ from "jquery";
import assert from "minimalistic-assert";
import SimpleBar from "simplebar";

// This type is helpful for testing, where we may have a dummy object instead of an actual jquery object.
type JQueryOrZJQuery = {__zjquery?: true} & JQuery;

export function get_content_element($element: JQuery): JQuery {
    const element = $element.expectOne()[0];
    const sb: unknown = SimpleBar.instances.get(element);
    if (sb) {
        assert(sb instanceof SimpleBar); // https://github.com/Grsmto/simplebar/pull/689
        return $(sb.getContentElement()!);
    }
    return $element;
}

export function get_scroll_element($element: JQueryOrZJQuery): JQuery {
    // For testing we just return the element itself.
    if ($element?.__zjquery) {
        return $element;
    }

    const element = $element.expectOne()[0];
    const sb: unknown = SimpleBar.instances.get(element);
    if (sb) {
        assert(sb instanceof SimpleBar); // https://github.com/Grsmto/simplebar/pull/689
        return $(sb.getScrollElement()!);
    } else if ("simplebar" in element.dataset) {
        // The SimpleBar mutation observer hasn’t processed this element yet.
        // Create the SimpleBar early in case we need to add event listeners.
        return $(new SimpleBar(element).getScrollElement()!);
    }
    return $element;
}

export function reset_scrollbar($element: JQuery): void {
    const element = $element.expectOne()[0];
    const sb: unknown = SimpleBar.instances.get(element);
    if (sb) {
        assert(sb instanceof SimpleBar); // https://github.com/Grsmto/simplebar/pull/689
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
    // This does the minimum amount of scrolling that is needed to make
    // the element visible.  It doesn't try to center the element, so
    // this will be non-intrusive to users when they already have
    // the element visible.
    $container = get_scroll_element($container);
    const elem_top = $elem.position().top - sticky_header_height;
    const elem_bottom = elem_top + ($elem.innerHeight() ?? 0);
    const container_height = ($container.height() ?? 0) - sticky_header_height;

    const opts = {
        elem_top,
        elem_bottom,
        container_height,
    };

    const delta = scroll_delta(opts);

    if (delta === 0) {
        return;
    }

    $container.scrollTop(($container.scrollTop() ?? 0) + delta);
}
