import $ from "jquery";
import assert from "minimalistic-assert";

import * as lightbox from "./lightbox.ts";
import * as overlays from "./overlays.ts";
import * as scroll_util from "./scroll_util.ts";
import * as util from "./util.ts";

// Stores the focused element ID when an overlay opens lightbox,
// so focus can be restored when the overlay is reopened.
let pending_restore_element_id: string | undefined;

export function get_and_clear_pending_restore_element_id(): string | undefined {
    const id = pending_restore_element_id;
    pending_restore_element_id = undefined;
    return id;
}

export type Context = {
    items_container_selector: string;
    items_list_selector: string;
    row_item_selector: string;
    box_item_selector: string;
    id_attribute_name: string;
    get_items_ids: () => string[];
    on_enter: () => void;
    on_delete: () => void;
};

export function row_with_focus(context: Context): JQuery {
    const $focused_item = $(`.${CSS.escape(context.box_item_selector)}:focus`);
    return $focused_item.parent(`.${CSS.escape(context.row_item_selector)}`);
}

export function activate_element(elem: HTMLElement, context: Context): void {
    $(`.${CSS.escape(context.box_item_selector)}`).removeClass("active");
    elem.classList.add("active");
    elem.focus({preventScroll: true});
}

export function get_focused_element_id(context: Context): string | undefined {
    return row_with_focus(context).attr(context.id_attribute_name);
}

export function focus_on_sibling_element(context: Context): void {
    const $next_row = row_after_focus(context);
    const $prev_row = row_before_focus(context);
    let elem_to_be_focused_id: string | undefined;

    // Try to get the next item in the list and 'focus' on it.
    // Use previous item as a fallback.
    if ($next_row.length > 0) {
        elem_to_be_focused_id = $next_row.attr(context.id_attribute_name);
    } else if ($prev_row.length > 0) {
        elem_to_be_focused_id = $prev_row.attr(context.id_attribute_name);
    }

    const $new_focus_element = get_element_by_id(elem_to_be_focused_id ?? "", context);
    if ($new_focus_element[0] !== undefined) {
        assert($new_focus_element[0].children[0] instanceof HTMLElement);
        activate_element($new_focus_element[0].children[0], context);
        scroll_util.scroll_element_into_container(
            $new_focus_element,
            $(`.${CSS.escape(context.items_list_selector)}`),
        );
    }
}

export function modals_handle_events(event_key: string, context: Context): void {
    initialize_focus(event_key, context);

    // This detects up arrow key presses when the overlay
    // is open and scrolls through.  If the focused element
    // extends above the visible area, first scroll to reveal
    // more of it before moving focus to the previous one.
    if (
        (event_key === "up_arrow" || event_key === "vim_up") &&
        !scroll_toward_visible(row_with_focus(context), "up", context) &&
        row_before_focus(context).length > 0
    ) {
        scroll_to_element(row_before_focus(context), context);
    }

    // This detects down arrow key presses when the overlay
    // is open and scrolls through.  If the focused element
    // extends below the visible area, first scroll to reveal
    // more of it before moving focus to the next one.
    if (
        (event_key === "down_arrow" || event_key === "vim_down") &&
        !scroll_toward_visible(row_with_focus(context), "down", context) &&
        row_after_focus(context).length > 0
    ) {
        scroll_to_element(row_after_focus(context), context);
    }

    if (event_key === "backspace" || event_key === "delete") {
        context.on_delete();
    }

    if (event_key === "enter") {
        context.on_enter();
    }
}

export function set_initial_element(element_id: string | undefined, context: Context): void {
    if (element_id) {
        const current_element = util.the(get_element_by_id(element_id, context));
        const focus_element = current_element.children[0];
        assert(focus_element instanceof HTMLElement);
        activate_element(focus_element, context);
        scroll_util.scroll_element_into_container(
            get_element_by_id(element_id, context),
            $(`.${CSS.escape(context.items_list_selector)}`),
        );
    }
}

// Like set_initial_element, but returns false instead of throwing
// when the element no longer exists (e.g., deleted while lightbox
// was open).
export function try_set_initial_element(element_id: string, context: Context): boolean {
    if (get_element_by_id(element_id, context).length === 0) {
        return false;
    }
    set_initial_element(element_id, context);
    return true;
}

function row_before_focus(context: Context): JQuery {
    const $focused_row = row_with_focus(context);
    const $prev_row = $focused_row.prev(`.${CSS.escape(context.row_item_selector)}`);
    // The draft modal can have two sub-sections. This handles the edge case
    // when the user moves from the second "Other drafts" section to the first
    // section which contains drafts from a particular narrow.
    if (
        $prev_row.length === 0 &&
        $focused_row.parent().attr("id") === "other-drafts" &&
        $("#drafts-from-conversation").css("display") !== "none"
    ) {
        return $($("#drafts-from-conversation").children(".overlay-message-row").last());
    }

    return $prev_row;
}

function row_after_focus(context: Context): JQuery {
    const $focused_row = row_with_focus(context);
    const $next_row = $focused_row.next(`.${CSS.escape(context.row_item_selector)}`);
    // The draft modal can have two sub-sections. This handles the edge case
    // when the user moves from the first section (drafts from a particular
    // narrow) to the second section which contains the rest of the drafts.
    if (
        $next_row.length === 0 &&
        $focused_row.parent().attr("id") === "drafts-from-conversation" &&
        $("#other-drafts").css("display") !== "none"
    ) {
        return $("#other-drafts").children(".overlay-message-row").first();
    }
    return $next_row;
}

function initialize_focus(event_name: string, context: Context): void {
    // If an item is not focused in modal, then focus the last item
    // if up_arrow is clicked or the first item if down_arrow is clicked.
    if (
        (event_name !== "up_arrow" && event_name !== "down_arrow") ||
        $(`.${CSS.escape(context.box_item_selector)}:focus`).length > 0
    ) {
        return;
    }

    const modal_items_ids = context.get_items_ids();
    const id = modal_items_ids.at(event_name === "up_arrow" ? -1 : 0);
    if (id === undefined) {
        // modal is empty
        return;
    }

    const $element = get_element_by_id(id, context);
    const focus_element = util.the($element).children[0];
    assert(focus_element instanceof HTMLElement);
    activate_element(focus_element, context);
    const $items_list = $(`.${CSS.escape(context.items_list_selector)}`);
    scroll_util.scroll_element_into_container($element, $items_list);
    return;
}

// When a focused element is taller than the scroll viewport (e.g. a long
// draft), pressing an arrow key should first scroll to reveal the hidden
// portion of the element before moving focus to the next one.  Returns
// true if the element extended beyond the viewport in the given direction
// and we scrolled within it.
//
// We use a 1px threshold to avoid getting trapped by sub-pixel rounding:
// at fractional scroll positions, row_top or row_bottom can be a fraction
// like -0.3 that never reaches exactly 0, causing infinite negligible
// scrolls that prevent moving to the adjacent element.
const SCROLL_THRESHOLD = 1;

function scroll_toward_visible(
    $focused_row: JQuery,
    direction: "up" | "down",
    context: Context,
): boolean {
    if ($focused_row.length === 0) {
        return false;
    }

    const $items_list = $(`.${CSS.escape(context.items_list_selector)}`);
    const $scroll_container = scroll_util.get_scroll_element($items_list);

    const row_offset = $focused_row.offset()?.top ?? 0;
    const container_offset = $scroll_container.offset()?.top ?? 0;
    const row_top = row_offset - container_offset;
    const row_bottom = row_top + ($focused_row.innerHeight() ?? 0);
    const container_height = $scroll_container.height() ?? 0;

    if (direction === "down" && row_bottom > container_height + SCROLL_THRESHOLD) {
        // Element extends below the visible area; scroll down by up to
        // one viewport height, or just enough to reach the bottom.
        const scroll_amount = Math.min(container_height, row_bottom - container_height);
        $scroll_container.scrollTop(($scroll_container.scrollTop() ?? 0) + scroll_amount);
        return true;
    }

    if (direction === "up" && row_top < -SCROLL_THRESHOLD) {
        // Element extends above the visible area; scroll up by up to
        // one viewport height, or just enough to reach the top.
        const scroll_amount = Math.min(container_height, -row_top);
        $scroll_container.scrollTop(($scroll_container.scrollTop() ?? 0) - scroll_amount);
        return true;
    }

    return false;
}

function scroll_to_element($element: JQuery, context: Context): void {
    if ($element[0] === undefined) {
        return;
    }
    if ($element[0].children[0] === undefined) {
        return;
    }
    assert($element[0].children[0] instanceof HTMLElement);
    activate_element($element[0].children[0], context);

    const $items_list = $(`.${CSS.escape(context.items_list_selector)}`);
    scroll_util.scroll_element_into_container($element, $items_list);
}

function get_element_by_id(id: string, context: Context): JQuery {
    return $(`.overlay-message-row[${CSS.escape(context.id_attribute_name)}='${CSS.escape(id)}']`);
}

export function handle_overlay_media_click(
    e: JQuery.ClickEvent,
    overlay_name: string,
    context?: Context,
    reopen_overlay?: () => void,
): boolean {
    const $img = $(e.target).closest("img");
    if ($img.length > 0) {
        e.stopPropagation();
        e.preventDefault();
        open_lightbox_from_overlay($img, overlay_name, context, reopen_overlay);
        return true;
    }

    const $video = $(e.target).closest("video");
    if ($video.length > 0) {
        e.stopPropagation();
        e.preventDefault();
        open_lightbox_from_overlay($video, overlay_name, context, reopen_overlay);
        return true;
    }

    return false;
}

function open_lightbox_from_overlay(
    $media: JQuery<HTMLMediaElement> | JQuery<HTMLImageElement>,
    overlay_name: string,
    context: Context | undefined,
    reopen_overlay: (() => void) | undefined,
): void {
    if (context) {
        pending_restore_element_id = get_focused_element_id(context);
    }
    overlays.close_overlay(overlay_name);
    if (reopen_overlay) {
        lightbox.handle_overlay_media_element_click($media, reopen_overlay);
    } else {
        lightbox.handle_inline_media_element_click($media, true);
    }
}
