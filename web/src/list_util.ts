import $ from "jquery";

const list_selectors = [
    "#stream_filters",
    "#left-sidebar-navigation-list",
    "#buddy-list-users-matching-view",
    "#buddy-list-other-users",
    "#buddy-list-participants",
];

export function inside_list(e: JQuery.KeyDownEvent): boolean {
    const $target = $(e.target);
    const in_list = $target.closest(list_selectors.join(", ")).length > 0;
    return in_list;
}

export function go_down(e: JQuery.KeyDownEvent): void {
    const $target = $(e.target);
    $target.closest("li").next().find("a").trigger("focus");
}

export function go_up(e: JQuery.KeyDownEvent): void {
    const $target = $(e.target);
    $target.closest("li").prev().find("a").trigger("focus");
}
