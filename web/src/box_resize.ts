import type {Instance} from "tippy.js";

import {media_breakpoints_num} from "./css_variables.ts";

type ResizeDirection =
    | "right"
    | "top"
    | "top_right"
    | "left"
    | "bottom_left"
    | "bottom_right"
    | "top_left"
    | "bottom";

type ResizeConfig = {
    directions: ResizeDirection[];
    handle_size?: number;
    disable_on_mobile?: boolean;
};

// This serves two purposes:
// 1. It prevents the user from expanding the box to the point that
//    it cannot be resized because the handles go out of the viewport.
// 2. Tippy defines a max-width of calc(100vw - 10px), so stretching the content beyond
//    that makes it look like it is overflowing from the tippy box.
// Source: https://github.com/atomiks/tippyjs/blob/ad85f6feb79cf6c5853c43bf1b2a50c4fa98e7a1/src/scss/index.scss#L7
const MINIMUM_DISTANCE_FROM_VIEWPORT = 5;

function attach_proportional_window_resize(
    box: HTMLElement,
    tippyInstance: Instance | undefined,
): () => void {
    let last_window_width = window.innerWidth;
    let last_window_height = window.innerHeight;

    const on_window_resize = (): void => {
        window.requestAnimationFrame(() => {
            const current_window_width = window.innerWidth;
            const current_window_height = window.innerHeight;

            const width_ratio = current_window_width / last_window_width;
            const height_ratio = current_window_height / last_window_height;
            const {
                left: box_left,
                width: box_width,
                top: box_top,
                height: box_height,
            } = box.getBoundingClientRect();

            // In case of Tippy, the box rect properties are the ones after resize,
            // whereas for a normal box we have to handle the resizing ourselves.
            // We just update the box dimensions to appear proportional to the original window's
            // dimensions in case of Tippy, whereas for a normal box, the dimensions are updated
            // in proportion to the previous window's dimensions.
            const new_width = Math.min(
                box_width * width_ratio,
                current_window_width - 2 * MINIMUM_DISTANCE_FROM_VIEWPORT,
            );
            const new_height = Math.min(
                box_height * height_ratio,
                current_window_height - 2 * MINIMUM_DISTANCE_FROM_VIEWPORT,
            );
            box.style.width = `${new_width}px`;
            box.style.height = `${new_height}px`;

            if (tippyInstance) {
                maybe_update_popper_instance(tippyInstance);
            } else {
                // Scale coordinates and compensate if the dimensions were clamped
                let new_left = box_left * width_ratio + (box_width * width_ratio - new_width) / 2;
                let new_top = box_top * height_ratio + (box_height * height_ratio - new_height) / 2;

                const max_left = current_window_width - new_width - MINIMUM_DISTANCE_FROM_VIEWPORT;
                const max_top = current_window_height - new_height - MINIMUM_DISTANCE_FROM_VIEWPORT;

                new_left = Math.max(MINIMUM_DISTANCE_FROM_VIEWPORT, Math.min(new_left, max_left));
                new_top = Math.max(MINIMUM_DISTANCE_FROM_VIEWPORT, Math.min(new_top, max_top));

                box.style.left = `${new_left}px`;
                box.style.top = `${new_top}px`;

                // In the normal-div case, we scale both the box's size and its
                // position (left/top) based on how much the window changed.
                // Because we are scaling relative to the previous window size,
                // we must update `last_window_width/height` after each resize.
                // Otherwise, the next resize would apply the ratio again from
                // an old window size and the box would drift or jump.

                // In the Tippy case, we do NOT control the position.
                // Popper recalculates the box's position every time based on
                // its anchor and viewport constraints. Since we only scale the
                // width/height in that mode (and never touch left/top), we do
                // not update the window baseline incrementally. The positioning
                // engine handles the window and thereby box resize automatically.
                last_window_width = current_window_width;
                last_window_height = current_window_height;
            }
        });
    };

    window.addEventListener("resize", on_window_resize);

    return () => {
        window.removeEventListener("resize", on_window_resize);
    };
}

export function make_resizable(
    config: ResizeConfig,
    box: HTMLElement,
    tippyInstance?: Instance,
): () => void {
    // $md_min is the breakpoint used by popover_menus to display the popover
    // as an overlay on setting show_as_overlay_on_mobile. We use
    // `media_breakpoints_num.md` to ensure consistency with that breakpoint.
    if (config.disable_on_mobile && window.innerWidth < media_breakpoints_num.md) {
        return () => {
            // do nothing for the cleanup
        };
    }
    const handle_size = config.handle_size ?? 10;
    // We ensure positioning context to attach the handlers
    // relative to the container we want to make resizable here.
    if (getComputedStyle(box).position === "static") {
        box.style.position = "relative";
    }

    for (const direction of config.directions) {
        const handle = document.createElement("div");
        handle.classList.add("resizable-box-handle");
        apply_handle_styles(handle, direction, handle_size);
        attach_resize_behavior(handle, box, direction, tippyInstance);

        box.append(handle);
    }

    return attach_proportional_window_resize(box, tippyInstance);
}

function apply_handle_styles(handle: HTMLElement, direction: ResizeDirection, size: number): void {
    // The common positioning, cursor styling and z-index related
    // styles are applied using classes defined in `box_resize.css`
    switch (direction) {
        case "right":
            handle.style.width = `${size}px`;
            handle.classList.add("right-handle");
            break;

        case "left":
            handle.style.width = `${size}px`;
            handle.classList.add("left-handle");
            break;

        case "top":
            handle.style.height = `${size}px`;
            handle.classList.add("top-handle");
            break;

        case "bottom":
            handle.style.height = `${size}px`;
            handle.classList.add("bottom-handle");
            break;

        case "top_right":
            handle.style.width = `${size}px`;
            handle.style.height = `${size}px`;
            handle.classList.add("top-right-handle");
            break;

        case "top_left":
            handle.style.width = `${size}px`;
            handle.style.height = `${size}px`;
            handle.classList.add("top-left-handle");
            break;

        case "bottom_right":
            handle.style.width = `${size}px`;
            handle.style.height = `${size}px`;
            handle.classList.add("bottom-right-handle");
            break;

        case "bottom_left":
            handle.style.width = `${size}px`;
            handle.style.height = `${size}px`;
            handle.classList.add("bottom-left-handle");
            break;
    }
}

// Re-calculating the popper positi;on is necessary
// for shift in the box's anchor point.
// In cases where we don't use popper, the recalibaration
// has to be done manually by updating the top/left properties
// of the box.
function maybe_update_popper_instance(tippyInstance: Instance | undefined): void {
    if (tippyInstance) {
        void tippyInstance.popperInstance?.update();
    }
}

type ResizeDimensionsConfig = {
    dx?: number;
    dy?: number;
    is_left_handle?: boolean;
    is_top_handle?: boolean;
    start_left: number;
    start_top: number;
    initial_width: number;
    initial_height: number;
};

function apply_resize(
    box: HTMLElement,
    tippyInstance: Instance | undefined,
    config: ResizeDimensionsConfig,
): void {
    if (config.dx !== undefined) {
        // A negative dx for the left handle equates to a positive
        // growth in the box's width.
        const growth_dx = config.is_left_handle ? -config.dx : config.dx;

        // Prevent the box from shrinking below 0 width
        const min_growth_x = -config.initial_width / 2;

        // The max growth is constrained by the closest horizontal window edge.
        const distance_to_left_edge = config.start_left;
        const distance_to_right_edge =
            window.innerWidth - (config.start_left + config.initial_width);
        const max_growth_x =
            Math.min(distance_to_left_edge, distance_to_right_edge) -
            MINIMUM_DISTANCE_FROM_VIEWPORT;
        const clamped_growth_x = Math.max(min_growth_x, Math.min(growth_dx, max_growth_x));

        // The multiplier is set to 2 for the drag-handle-to-resize action so that
        // the box follows the cursor and doesn't lag behind when we change it's
        // width by 2*growth_dx while also updating the anchor for the box via box.style.left.
        box.style.width = `${config.initial_width + 2 * clamped_growth_x}px`;
        if (!tippyInstance) {
            box.style.left = `${config.start_left - clamped_growth_x}px`;
        }
    }

    if (config.dy !== undefined) {
        const growth_dy = config.is_top_handle ? -config.dy : config.dy;

        // Prevent the box from shrinking below 0 height.
        const min_growth_y = -config.initial_height / 2;

        // The max growth here is constrained by the closest vertical window edge.
        const distance_to_top_edge = config.start_top;
        const distance_to_bottom_edge =
            window.innerHeight - (config.start_top + config.initial_height);
        const max_growth_y =
            Math.min(distance_to_top_edge, distance_to_bottom_edge) -
            MINIMUM_DISTANCE_FROM_VIEWPORT;

        const clamped_growth_y = Math.max(min_growth_y, Math.min(growth_dy, max_growth_y));
        box.style.height = `${config.initial_height + 2 * clamped_growth_y}px`;
        if (!tippyInstance) {
            box.style.top = `${config.start_top - clamped_growth_y}px`;
        }
    }

    maybe_update_popper_instance(tippyInstance);
}

function attach_resize_behavior(
    handle: HTMLElement,
    box: HTMLElement,
    direction: ResizeDirection,
    tippyInstance: Instance | undefined,
): void {
    let start_x = 0;
    let start_y = 0;
    let initial_box_width = 0;
    let initial_box_height = 0;
    let start_left = 0;
    let start_top = 0;

    handle.addEventListener("pointerdown", (e: PointerEvent) => {
        e.preventDefault();

        start_x = e.clientX;
        start_y = e.clientY;

        const rect = box.getBoundingClientRect();
        initial_box_width = rect.width;
        initial_box_height = rect.height;
        start_left = rect.left;
        start_top = rect.top;

        handle.setPointerCapture(e.pointerId);

        handle.addEventListener("pointermove", on_pointer_move);
        handle.addEventListener("pointerup", on_pointer_up);
    });

    function on_pointer_move(e: PointerEvent): void {
        const dx = e.clientX - start_x;
        const dy = e.clientY - start_y;

        const base_config = {
            start_left,
            start_top,
            initial_width: initial_box_width,
            initial_height: initial_box_height,
        };

        switch (direction) {
            case "right":
                apply_resize(box, tippyInstance, {...base_config, dx});
                break;
            case "left":
                apply_resize(box, tippyInstance, {...base_config, dx, is_left_handle: true});
                break;
            case "bottom":
                apply_resize(box, tippyInstance, {...base_config, dy});
                break;
            case "top":
                apply_resize(box, tippyInstance, {...base_config, dy, is_top_handle: true});
                break;
            case "top_right":
                apply_resize(box, tippyInstance, {...base_config, dx, dy, is_top_handle: true});
                break;
            case "bottom_right":
                apply_resize(box, tippyInstance, {...base_config, dx, dy});
                break;
            case "bottom_left":
                apply_resize(box, tippyInstance, {...base_config, dx, dy, is_left_handle: true});
                break;
            case "top_left":
                apply_resize(box, tippyInstance, {
                    ...base_config,
                    dx,
                    dy,
                    is_left_handle: true,
                    is_top_handle: true,
                });
                break;
        }
    }

    function on_pointer_up(e: PointerEvent): void {
        handle.releasePointerCapture(e.pointerId);

        handle.removeEventListener("pointermove", on_pointer_move);
        handle.removeEventListener("pointerup", on_pointer_up);
    }
}
