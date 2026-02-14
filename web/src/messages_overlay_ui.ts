import $ from "jquery";
import assert from "minimalistic-assert";

import * as scroll_util from "./scroll_util.ts";
import * as util from "./util.ts";

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
    elem.focus();
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
    }
}

export function modals_handle_events(event_key: string, context: Context): void {
    const had_focus = row_with_focus(context).length > 0;
    initialize_focus(event_key, context);
    const has_focus = row_with_focus(context).length > 0;

    // This detects up arrow key presses when the overlay
    // is open and scrolls through.
    if (event_key === "up_arrow" || event_key === "vim_up") {
        if (has_focus) {
            if (!had_focus) {
                scroll_to_element(row_with_focus(context), context);
            } else {
                const $focused_row = row_with_focus(context);
                const $items_list = $(`.${CSS.escape(context.items_list_selector)}`);
                if (should_scroll_within_row($focused_row, $items_list, -1)) {
                    // Keep the scroll behavior symmetric with the down-arrow path
                    // to avoid jumpy upward scrolling for tall rows.
                    scroll_list_by_arrow(context, -1);
                } else {
                    scroll_to_element(row_before_focus(context), context);
                }
            }
        } else {
            scroll_list_by_arrow(context, -1);
        }
    }

    // This detects down arrow key presses when the overlay
    // is open and scrolls through.
    if (event_key === "down_arrow" || event_key === "vim_down") {
        if (has_focus) {
            if (!had_focus) {
                scroll_to_element(row_with_focus(context), context);
            } else {
                const $focused_row = row_with_focus(context);
                const $items_list = $(`.${CSS.escape(context.items_list_selector)}`);
                if (should_scroll_within_row($focused_row, $items_list, 1)) {
                    scroll_list_by_arrow(context, 1);
                } else {
                    scroll_to_element(row_after_focus(context), context);
                }
            }
        } else {
            scroll_list_by_arrow(context, 1);
        }
    }

    if (event_key === "backspace" || event_key === "delete") {
        context.on_delete();
    }

    if (event_key === "enter") {
        context.on_enter();
    }
}

function scroll_list_by_arrow(context: Context, direction: -1 | 1): void {
    const active_element = document.activeElement;
    if (
        active_element instanceof HTMLElement &&
        (active_element.tagName === "INPUT" ||
            active_element.tagName === "TEXTAREA" ||
            active_element.isContentEditable)
    ) {
        return;
    }

    const $items_list = $(`.${CSS.escape(context.items_list_selector)}`);
    if ($items_list.length === 0) {
        return;
    }

    const $scroll_element = scroll_util.get_scroll_element($items_list);
    const scroll_element = util.the($scroll_element);
    const step = Math.max(32, Math.round(scroll_element.clientHeight * 0.1));
    const prefers_reduced_motion =
        window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const behavior: ScrollBehavior = prefers_reduced_motion ? "auto" : "smooth";
    scroll_element.scrollBy({top: direction * step, behavior});
}

function should_scroll_within_row($row: JQuery, $items_list: JQuery, direction: -1 | 1): boolean {
    if ($row.length === 0 || $items_list.length === 0) {
        return false;
    }

    const scroll_element = util.the(scroll_util.get_scroll_element($items_list));
    const view_rect = scroll_element.getBoundingClientRect();
    const row_rect = util.the($row).getBoundingClientRect();
    const view_height = view_rect.bottom - view_rect.top;

    if (row_rect.height <= view_height) {
        return false;
    }

    const PADDING_BOTTOM = 12;
    const PADDING_TOP = 4;
    if (direction === 1) {
        return row_rect.bottom > view_rect.bottom + PADDING_BOTTOM;
    }
    return row_rect.top < view_rect.top - PADDING_TOP;
}

export function set_initial_element(element_id: string | undefined, context: Context): void {
    if (element_id) {
        const current_element = util.the(get_element_by_id(element_id, context));
        const focus_element = current_element.children[0];
        assert(focus_element instanceof HTMLElement);
        activate_element(focus_element, context);
        scroll_util.scroll_element_into_container(
            $(focus_element),
            $(`.${CSS.escape(context.items_list_selector)}`),
        );
    }
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
    const $box_item = $(`.${CSS.escape(context.box_item_selector)}`);
    const $scroll_element = scroll_util.get_scroll_element($items_list);
    const scroll_element = util.the($scroll_element);
    const prefers_reduced_motion =
        window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const behavior: ScrollBehavior = prefers_reduced_motion ? "auto" : "smooth";
    const section_id = $element.parent().attr("id");
    const is_first_in_section =
        $element.parent().children().first()[0] !== undefined &&
        $element.parent().children().first()[0] === $element[0];
    const is_section_boundary =
        (section_id === "drafts-from-conversation" || section_id === "other-drafts") &&
        is_first_in_section;

    // When crossing between draft sections, align the first row of the new section
    // to the top of the list so navigation starts from the beginning, not the end.
    if (is_section_boundary) {
        const view_top = scroll_element.getBoundingClientRect().top;
        const elem_top = $element[0].getBoundingClientRect().top;
        const delta = elem_top - view_top;
        if (Math.abs(delta) > 2) {
            scroll_element.scrollTo({top: scroll_element.scrollTop + delta, behavior});
        }
        return;
    }

    // If focused element is first, scroll to the top.
    if (util.the($box_item.first()).parentElement === $element[0]) {
        const view_rect = scroll_element.getBoundingClientRect();
        const row_rect = $element[0].getBoundingClientRect();
        const view_height = view_rect.bottom - view_rect.top;
        if (row_rect.height > view_height) {
            const delta = row_rect.bottom - view_rect.bottom;
            scroll_element.scrollTo({top: scroll_element.scrollTop + delta, behavior});
        } else {
            scroll_element.scrollTo({top: 0, behavior});
        }
        return;
    }
    // If focused element is last, scroll to the bottom.
    if (util.the($box_item.last()).parentElement === $element[0]) {
        const view_rect = scroll_element.getBoundingClientRect();
        const row_rect = $element[0].getBoundingClientRect();
        const view_height = view_rect.bottom - view_rect.top;
        if (row_rect.height > view_height) {
            const delta = row_rect.top - view_rect.top;
            scroll_element.scrollTo({top: scroll_element.scrollTop + delta, behavior});
        } else {
            scroll_element.scrollTo({
                top: scroll_element.scrollHeight - scroll_element.clientHeight,
                behavior,
            });
        }
        return;
    }

    scroll_util.scroll_element_into_container($element, $items_list);
}

function get_element_by_id(id: string, context: Context): JQuery {
    return $(`.overlay-message-row[${CSS.escape(context.id_attribute_name)}='${CSS.escape(id)}']`);
}
