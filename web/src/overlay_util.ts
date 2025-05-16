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

export function trap_focus(overlay: JQuery): void {
    // Add these classes with tabindex="0" at top and bottom of the
    // overlays to enable the focus trapping.
    const $top_focus_trapper = overlay.find(".top-focus-trapper");
    const $bottom_focus_trapper = overlay.find(".bottom-focus-trapper");

    // Traps the Shift + Tab key to loop to the bottom
    $top_focus_trapper.on("keydown", (e: JQuery.KeyDownEvent) => {
        if (e.key === "Tab" && e.shiftKey) {
            e.preventDefault();
            $bottom_focus_trapper.trigger("focus");
        }
    });

    // Traps the Tab key to loop to the top
    $bottom_focus_trapper.on("keydown", (e: JQuery.KeyDownEvent) => {
        if (e.key === "Tab" && !e.shiftKey) {
            e.preventDefault();
            $top_focus_trapper.trigger("focus");
        }
    });
}
