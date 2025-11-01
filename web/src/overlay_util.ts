import $ from "jquery";

export function disable_scrolling(): void {
    // Why disable scrolling?
    // Since fixed / absolute positioned elements don't capture the scroll event unless
    // they overflow their defined container. Since fixed / absolute elements are not treated
    // as part of the document flow, we cannot capture `scroll` events on them and prevent propagation
    // as event bubbling doesn't work naturally.
    const scrollbar_width = window.innerWidth - document.documentElement.clientWidth;
    $(":root")
        .addClass("overflow-y-hidden")
        .css("--disabled-scrollbar-width", `${scrollbar_width}px`);
}

export function enable_scrolling(): void {
    $(":root").removeClass("overflow-y-hidden").css("--disabled-scrollbar-width", "0px");
}
