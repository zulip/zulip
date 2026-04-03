import $ from "jquery";

export function disable_scrolling(): void {
    // Why disable scrolling?
    // Since fixed / absolute positioned elements don't capture the scroll event unless
    // they overflow their defined container. Since fixed / absolute elements are not treated
    // as part of the document flow, we cannot capture `scroll` events on them and prevent propagation
    // as event bubbling doesn't work naturally.
    const scrollbar_width = window.innerWidth - document.documentElement.clientWidth;
    $(":root").css({"overflow-y": "hidden", "--disabled-scrollbar-width": `${scrollbar_width}px`});
}

export function enable_scrolling(): void {
    $(":root").css({"overflow-y": "scroll", "--disabled-scrollbar-width": "0px"});
}

export function get_visible_focusable_elements_in_overlay_container(
    $container: JQuery,
): HTMLElement[] {
    const visible_focusable_elements = [
        ...$container.find(
            "input, button, select, .input, .sidebar-item, .ind-tab.first, a[href], a[tabindex='0']",
        ),
    ].filter(
        (element) =>
            element.getClientRects().length > 0 && $(element).css("visibility") !== "hidden",
    );
    return visible_focusable_elements;
}
