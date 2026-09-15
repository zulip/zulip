import {$} from "jquery";

import * as scroll_util from "./scroll_util.ts";
import * as util from "./util.ts";

// The button floating over the bottom of the zoomed-in topic list,
// which jumps to the resolved topics in channels that list them
// after the unresolved ones.

let get_scroll_container: () => JQuery;
let get_topic_items: () => JQuery;

let modal_resize_observer: ResizeObserver | undefined;
// The first resolved topic row in the zoomed-in topic list, when the
// resolved topics button applies. It only changes when the list is
// rebuilt, so we search the rows for it then rather than on every
// scroll event.
let $first_resolved_topic_row: JQuery | undefined;

// Height of the button, which rows scrolled into view should clear.
export function get_height(): number {
    const $jump_button = $("#more-topics-modal .resolved-topics-jump");
    if (!$jump_button.hasClass("show")) {
        return 0;
    }
    return $jump_button.outerHeight(true) ?? 0;
}

// The first resolved topic with unreads, or else the first resolved
// topic, which is where the resolved topics button jumps to.
function get_jump_target_row(): JQuery | undefined {
    const $first_unread_resolved_topic_row = get_topic_items()
        .filter(".unmuted-resolved-topic-with-unreads")
        .first();
    if ($first_unread_resolved_topic_row.length > 0) {
        return $first_unread_resolved_topic_row;
    }
    return $first_resolved_topic_row;
}

// The first resolved topic row in the zoomed-in topic list, or
// undefined when the resolved topics button does not apply: when the
// channel does not list resolved topics last, or when the list has
// no resolved topics.
function find_first_resolved_topic_row(resolved_topics_last: boolean): JQuery | undefined {
    if (!resolved_topics_last) {
        return undefined;
    }
    const $first_row = get_topic_items().filter(".resolved-topic").first();
    return $first_row.length > 0 ? $first_row : undefined;
}

// Says whether the resolved topics have unreads.
function update_label(): void {
    const has_unreads = get_topic_items().filter(".unmuted-resolved-topic-with-unreads").length > 0;
    const $jump_button = $("#more-topics-modal .resolved-topics-jump");
    $jump_button.find(".resolved-topics-jump-unread-label").toggleClass("hide", !has_unreads);
    $jump_button.find(".resolved-topics-jump-label").toggleClass("hide", has_unreads);
}

// Shows the resolved topics button while no resolved topic is in
// view, i.e. while the first one is below the visible rows.
function update_visibility(): void {
    const $jump_button = $("#more-topics-modal .resolved-topics-jump");
    if ($first_resolved_topic_row === undefined) {
        $jump_button.removeClass("show");
        return;
    }
    const $scroll_container = get_scroll_container();
    const container_bottom = util.the($scroll_container).getBoundingClientRect().bottom;
    const row_bottom = util.the($first_resolved_topic_row).getBoundingClientRect().bottom;
    $jump_button.toggleClass("show", row_bottom > container_bottom);
}

function scroll_to_resolved_topics(): void {
    const $target_row = get_jump_target_row();
    // The button stays clickable while it fades out, and a rebuild
    // may have removed the resolved topics in the meantime.
    if ($target_row === undefined) {
        return;
    }

    // Scroll the target row to the top of the topic list, unlike
    // scroll_element_into_container, which only scrolls until the
    // row is visible.
    const $scroll_container = scroll_util.get_scroll_element(get_scroll_container());
    const row_offset = $target_row.offset()!.top;
    const container_offset = $scroll_container.offset()!.top;
    $scroll_container.animate(
        {scrollTop: $scroll_container.scrollTop()! + row_offset - container_offset},
        "fast",
    );
}

// Called when the zoomed-in topic list is rebuilt, with whether its
// channel lists resolved topics last.
export function update_for_rebuilt_topic_list(resolved_topics_last: boolean): void {
    $first_resolved_topic_row = find_first_resolved_topic_row(resolved_topics_last);
    update_label();
    update_visibility();
}

function disconnect_modal_resize_observer(): void {
    modal_resize_observer?.disconnect();
    modal_resize_observer = undefined;
}

export function handle_zoom_in(): void {
    // The scroll container is recreated on each zoom in, so this
    // listener goes away with it.
    scroll_util.get_scroll_element(get_scroll_container()).on("scroll", update_visibility);
    // Recompute the button's visibility when the sidebar is resized.
    disconnect_modal_resize_observer();
    modal_resize_observer = new ResizeObserver(update_visibility);
    modal_resize_observer.observe(util.the($("#more-topics-modal")));
}

export function handle_zoom_out(): void {
    disconnect_modal_resize_observer();
    $first_resolved_topic_row = undefined;
}

export function initialize(opts: {
    get_scroll_container: () => JQuery;
    get_topic_items: () => JQuery;
}): void {
    get_scroll_container = opts.get_scroll_container;
    get_topic_items = opts.get_topic_items;

    $("body").on("click", "#more-topics-modal .resolved-topics-jump", (e) => {
        e.preventDefault();
        e.stopPropagation();
        scroll_to_resolved_topics();
    });
}
