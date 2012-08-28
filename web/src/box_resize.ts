// Attach resize handles to a centered box. The caller keeps the box
// centered (via CSS, or via the `on_resize` callback for a Tippy
// overlay that needs `popperInstance.update()` after each change).
// Because the box stays centered, dragging one edge by `delta` grows
// the box by `2 * delta` so the cursor tracks the dragged edge.
// Size bounds and any mobile-disable behavior live in CSS.

type Direction =
    | "top"
    | "right"
    | "bottom"
    | "left"
    | "top_left"
    | "top_right"
    | "bottom_left"
    | "bottom_right";

type HandleSpec = {
    grows_width: boolean;
    grows_height: boolean;
    // -1 for handles on the left/top edge, whose pointer moves in the
    // negative direction to grow the box.
    dx_sign: 1 | -1;
    dy_sign: 1 | -1;
};

const HANDLE_SPECS: Record<Direction, HandleSpec> = {
    right: {grows_width: true, grows_height: false, dx_sign: 1, dy_sign: 1},
    left: {grows_width: true, grows_height: false, dx_sign: -1, dy_sign: 1},
    bottom: {grows_width: false, grows_height: true, dx_sign: 1, dy_sign: 1},
    top: {grows_width: false, grows_height: true, dx_sign: 1, dy_sign: -1},
    bottom_right: {grows_width: true, grows_height: true, dx_sign: 1, dy_sign: 1},
    bottom_left: {grows_width: true, grows_height: true, dx_sign: -1, dy_sign: 1},
    top_right: {grows_width: true, grows_height: true, dx_sign: 1, dy_sign: -1},
    top_left: {grows_width: true, grows_height: true, dx_sign: -1, dy_sign: -1},
};

export function make_resizable(
    box: HTMLElement,
    directions: Direction[],
    on_resize?: () => void,
): () => void {
    const handles: HTMLElement[] = [];
    for (const direction of directions) {
        const handle = document.createElement("div");
        handle.classList.add(
            "resizable-box-handle",
            `resizable-box-handle-${direction.replaceAll("_", "-")}`,
        );
        attach_handle(handle, box, HANDLE_SPECS[direction], on_resize);
        box.append(handle);
        handles.push(handle);
    }
    return () => {
        for (const handle of handles) {
            handle.remove();
        }
    };
}

function parse_px_bound(value: string, fallback: number): number {
    if (value === "" || value === "auto" || value === "none") {
        return fallback;
    }
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function clamp(value: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, value));
}

function attach_handle(
    handle: HTMLElement,
    box: HTMLElement,
    spec: HandleSpec,
    on_resize: (() => void) | undefined,
): void {
    let start_x = 0;
    let start_y = 0;
    let start_width = 0;
    let start_height = 0;

    function on_pointer_move(e: PointerEvent): void {
        // Clamp against CSS bounds so dragging past min/max doesn't
        // build up an invisible overshoot the user then has to drag
        // back through before the box starts responding again.
        const style = getComputedStyle(box);
        if (spec.grows_width) {
            const delta = spec.dx_sign * (e.clientX - start_x);
            const min_width = parse_px_bound(style.minWidth, 0);
            const max_width = parse_px_bound(style.maxWidth, Number.POSITIVE_INFINITY);
            box.style.width = `${clamp(start_width + 2 * delta, min_width, max_width)}px`;
        }
        if (spec.grows_height) {
            const delta = spec.dy_sign * (e.clientY - start_y);
            const min_height = parse_px_bound(style.minHeight, 0);
            const max_height = parse_px_bound(style.maxHeight, Number.POSITIVE_INFINITY);
            box.style.height = `${clamp(start_height + 2 * delta, min_height, max_height)}px`;
        }
        on_resize?.();
    }

    function end_drag(e: PointerEvent): void {
        handle.releasePointerCapture(e.pointerId);
        handle.removeEventListener("pointermove", on_pointer_move);
        handle.removeEventListener("pointerup", end_drag);
        // `pointercancel` fires when the browser takes the gesture
        // away from us (palm rejection, alt-tab, etc.); without
        // cleaning up, `pointermove` would keep resizing the box.
        handle.removeEventListener("pointercancel", end_drag);
    }

    handle.addEventListener("pointerdown", (e: PointerEvent) => {
        e.preventDefault();
        const rect = box.getBoundingClientRect();
        start_x = e.clientX;
        start_y = e.clientY;
        start_width = rect.width;
        start_height = rect.height;
        handle.setPointerCapture(e.pointerId);
        handle.addEventListener("pointermove", on_pointer_move);
        handle.addEventListener("pointerup", end_drag);
        handle.addEventListener("pointercancel", end_drag);
    });
}
