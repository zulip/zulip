import $ from "jquery";

export function disable_scrolling(): void {
    // Why disable scrolling?
    // Since fixed / absolute positioned elements don't capture the scroll event unless
    // they overflow their defined container. Since fixed / absolute elements are not treated
    // as part of the document flow, we cannot capture `scroll` events on them and prevent propagation
    // as event bubbling doesn't work naturally.
    const scrollbar_width = window.innerWidth - document.documentElement.clientWidth;
    $("html").css({"overflow-y": "hidden", "--disabled-scrollbar-width": `${scrollbar_width}px`});
}

export function enable_scrolling(): void {
    $("html").css({"overflow-y": "scroll", "--disabled-scrollbar-width": "0px"});
}

/*
 * Trap keyboard focus within an overlay container with visible focus indicators
 */
export function trap_focus($container: JQuery): () => void {
    const $focusable_elements = $container
        .find('a[href], button, input, textarea, select, [tabindex]:not([tabindex="-1"])')
        .filter(":visible");
    const $first_focusable = $focusable_elements.first();
    const $last_focusable = $focusable_elements.last();

    const $start_sentinel = $(document.createElement("div"))
        .attr("tabindex", "0")
        .attr("aria-hidden", "true")
        .addClass("focus-sentinel");
    const $end_sentinel = $(document.createElement("div"))
        .attr("tabindex", "0")
        .attr("aria-hidden", "true")
        .addClass("focus-sentinel");

    $container.prepend($start_sentinel);
    $container.append($end_sentinel);

    const handle_focus = (e: JQuery.TriggeredEvent): void => {
        if (e.target === $start_sentinel[0] && $last_focusable.length > 0) {
            $last_focusable[0]!.focus();
        } else if (e.target === $end_sentinel[0] && $first_focusable.length > 0) {
            $first_focusable[0]!.focus();
        }
    };

    $start_sentinel.on("focus", handle_focus);
    $end_sentinel.on("focus", handle_focus);

    setTimeout(() => {
        if ($first_focusable.length > 0) {
            $first_focusable[0]!.focus({preventScroll: true});
        } else {
            $container.attr("tabindex", "0");
            $container[0]!.focus({preventScroll: true});
        }
    }, 0);

    return () => {
        $start_sentinel.off("focus", handle_focus).remove();
        $end_sentinel.off("focus", handle_focus).remove();
    };
}
