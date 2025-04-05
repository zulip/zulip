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
    const $focusableElements = $container
        .find('a[href], button, input, textarea, select, [tabindex]:not([tabindex="-1"])')
        .filter(":visible");
    const $firstFocusable = $focusableElements.first();
    const $lastFocusable = $focusableElements.last();

    const $startSentinel = $(document.createElement("div"))
        .attr("tabindex", "0")
        .attr("aria-hidden", "true")
        .addClass("focus-sentinel");
    const $endSentinel = $(document.createElement("div"))
        .attr("tabindex", "0")
        .attr("aria-hidden", "true")
        .addClass("focus-sentinel");

    $container.prepend($startSentinel);
    $container.append($endSentinel);

    const handleFocus = (e: JQuery.TriggeredEvent): void => {
        if (e.target === $startSentinel[0] && $lastFocusable.length > 0) {
            $lastFocusable[0]!.focus();
        } else if (e.target === $endSentinel[0] && $firstFocusable.length > 0) {
            $firstFocusable[0]!.focus();
        }
    };

    $startSentinel.on("focus", handleFocus);
    $endSentinel.on("focus", handleFocus);

    setTimeout(() => {
        if ($firstFocusable.length > 0) {
            $firstFocusable[0]!.focus({preventScroll: true});
        } else {
            $container.attr("tabindex", "0");
            $container[0]!.focus({preventScroll: true});
        }
    }, 0);

    return () => {
        $startSentinel.off("focus", handleFocus).remove();
        $endSentinel.off("focus", handleFocus).remove();
    };
}
