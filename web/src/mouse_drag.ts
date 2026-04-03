import $ from "jquery";

let start_x = 0;
let start_y = 0;

export function initialize(): void {
    $(document).on("pointerdown", (e) => {
        start_x = e.pageX ?? 0;
        start_y = e.pageY ?? 0;
    });
}

export function is_drag(e: JQuery.ClickEvent): boolean {
    // Used to prevent click handlers from firing when dragging a
    // region, even if not actually selecting something.

    if (!e.originalEvent?.isTrusted) {
        return false;
    }

    // Modern browsers dispatch click as a PointerEvent. Keyboard-
    // triggered clicks (e.g. Enter on a focused link) have an empty
    // pointerType, so we can skip drag detection for them.
    if (e.originalEvent instanceof PointerEvent && e.originalEvent.pointerType === "") {
        return false;
    }

    // Total distance the mouse has moved since the mouse went down.
    const drag_distance = Math.abs(e.pageX - start_x) + Math.abs(e.pageY - start_y);

    const sel = window.getSelection();
    const has_selection = sel?.type === "Range" && sel.toString().length > 0;

    // A very low drag_distance cutoff (2) can prevent a click after
    // moving the mouse rapidly from registering.
    //
    // So we only use that low cutoff when the drag resulted in
    // actually selecting something, and use a larger distance for
    // non-selection drags, like resizing textareas.
    return drag_distance > 20 || (drag_distance > 2 && has_selection);
}
