import $ from "jquery";

// We've changed the buddy_list (#user_presences) to use div#user_presences > div.user_presence
// instead of ul > lis, and as such we need to replace this as well, however, everything
// seems to work fine without it, so the purpose of these helpers is not clear.

const list_selectors = ["#stream_filters", "#global_filters", "#user_presences"];

export function inside_list(e: JQuery.KeyDownEvent | JQuery.KeyPressEvent): boolean {
    const $target = $(e.target);
    const in_list = $target.closest(list_selectors.join(", ")).length > 0;
    return in_list;
}

export function go_down(e: JQuery.KeyDownEvent | JQuery.KeyPressEvent): void {
    const $target = $(e.target);
    $target.closest("li").next().find("a").trigger("focus");
}

export function go_up(e: JQuery.KeyDownEvent | JQuery.KeyPressEvent): void {
    const $target = $(e.target);
    $target.closest("li").prev().find("a").trigger("focus");
}
