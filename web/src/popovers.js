import $ from "jquery";

export function any_active() {
    const $tippy_instances = $("[data-tippy-root]");
    // tippy instances without `interactive: true` have `pointer-events: none`.
    const any_interactive_instances = $tippy_instances.filter(
        (_i, elt) => elt.style.pointerEvents === "",
    ).length;
    const is_sidebar_expanded = $("[class^='column-'].expanded").length;
    return Boolean(any_interactive_instances || is_sidebar_expanded);
}
