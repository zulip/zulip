import $ from "jquery";
import SimpleBar from "simplebar/dist/simplebar";

export function get_content_element(element_selector) {
    const element = element_selector.expectOne()[0];
    const sb = SimpleBar.instances.get(element);
    if (sb) {
        return $(sb.getContentElement());
    }
    return element_selector;
}

export function get_scroll_element(element_selector) {
    const element = element_selector.expectOne()[0];
    const sb = SimpleBar.instances.get(element);
    if (sb) {
        return $(sb.getScrollElement());
    } else if ("simplebar" in element.dataset) {
        // The SimpleBar mutation observer hasn’t processed this element yet.
        // Create the SimpleBar early in case we need to add event listeners.
        return $(new SimpleBar(element).getScrollElement());
    }
    return element_selector;
}

export function reset_scrollbar(element_selector) {
    const element = element_selector.expectOne()[0];
    const sb = SimpleBar.instances.get(element);
    if (sb) {
        sb.getScrollElement().scrollTop = 0;
    } else {
        element.scrollTop = 0;
    }
}
