import * as util from "./util.ts";

// Toggles `sidebar-header-drop-shadow` on sticky headers inside a scroll
// container while the container is scrolled and the header is pinned at
// its sticky top. The shadow is suppressed once the header's top has been
// pushed above the pin line by the next section arriving from below, to
// avoid a visible border at their junction.

export function initialize($scroll_container: JQuery, header_selector: string): void {
    const scroll_container = util.the($scroll_container);
    function update(): void {
        const has_scrolled = scroll_container.scrollTop > 0;
        const container_top = scroll_container.getBoundingClientRect().top;
        for (const header of scroll_container.querySelectorAll<HTMLElement>(header_selector)) {
            const sticky_top = Number.parseFloat(getComputedStyle(header).top) || 0;
            const pushed_past_pin_line =
                container_top + sticky_top - header.getBoundingClientRect().top;
            const is_stuck = has_scrolled && pushed_past_pin_line > -1 && pushed_past_pin_line <= 2;
            header.classList.toggle("sidebar-header-drop-shadow", is_stuck);
        }
    }
    scroll_container.addEventListener("scroll", update, {passive: true});
    update();
}
