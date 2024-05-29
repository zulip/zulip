import $ from "jquery";
import assert from "minimalistic-assert";

import * as blueslip from "./blueslip";
import * as message_lists from "./message_lists";
import * as message_scroll_state from "./message_scroll_state";
import type {Message} from "./message_store";
import * as rows from "./rows";
import * as util from "./util";

type MessageViewportInfo = {
    visible_top: number;
    visible_bottom: number;
    visible_height: number;
};

export const $scroll_container = $("html");

let in_stoppable_autoscroll = false;

const cached_width = new util.CachedValue({compute_value: () => $scroll_container.width() ?? 0});
const cached_height = new util.CachedValue({compute_value: () => $scroll_container.height() ?? 0});
export const width = cached_width.get.bind(cached_width);
export const height = cached_height.get.bind(cached_height);

// TODO: This function lets us use the DOM API instead of jquery
// (<10x faster) for condense.js, but we want to eventually do a
// bigger of refactor `height` and `width` above to do the same.
export function max_message_height(): number {
    return document.querySelector("html")!.offsetHeight * 0.65;
}

// Includes both scroll and arrow events. Negative means scroll up,
// positive means scroll down.
export let last_movement_direction = 1;

export function set_last_movement_direction(value: number): void {
    last_movement_direction = value;
}

export function at_rendered_top(): boolean {
    return scrollTop() <= 0;
}

export function message_viewport_info(): MessageViewportInfo {
    // Return a structure that tells us details of the viewport
    // accounting for fixed elements like the top navbar.
    //
    // Sticky message_header is NOT considered to be part of the visible
    // message pane, which should make sense for callers, who will
    // generally be concerned about whether actual message content is
    // visible.
    const $element_just_above_us = $("#navbar-fixed-container");
    const $element_just_below_us = $("#compose");

    let visible_top = $element_just_above_us.outerHeight() ?? 0;

    const $sticky_header = $(".sticky_header");
    if ($sticky_header.length) {
        visible_top += $sticky_header.outerHeight() ?? 0;
    }

    const visible_bottom = $element_just_below_us.position().top;

    const visible_height = visible_bottom - visible_top;

    return {
        visible_top,
        visible_bottom,
        visible_height,
    };
}

// Important note: These functions just look at the state of the
// rendered message feed; messages that are not displayed due to a
// limited render window or because they have not been fetched from
// the server are not considered.
export function at_rendered_bottom(): boolean {
    const bottom = scrollTop() + height();
    // This also includes bottom whitespace.
    const full_height = $scroll_container[0].scrollHeight;

    // We only know within a pixel or two if we're
    // exactly at the bottom, due to browser quirkiness,
    // and we err on the side of saying that we are at
    // the bottom.
    return bottom + 2 >= full_height;
}

// This differs from at_rendered_bottom in that it only requires the
// bottom message to be visible, but you may be able to scroll down
// further to see the rest of that message.
export function bottom_rendered_message_visible(): boolean {
    const $last_row = rows.last_visible();
    if ($last_row.length) {
        const message_bottom = $last_row[0].getBoundingClientRect().bottom;
        const bottom_of_feed = $("#compose")[0].getBoundingClientRect().top;
        return bottom_of_feed > message_bottom;
    }
    return false;
}

export function is_below_visible_bottom(offset: number): boolean {
    return offset > scrollTop() + height() - ($("#compose").height() ?? 0);
}

export function is_scrolled_up(): boolean {
    // Let's determine whether the user was already dealing
    // with messages off the screen, which can guide auto
    // scrolling decisions.
    const $last_row = rows.last_visible();
    if ($last_row.length === 0) {
        return false;
    }

    const offset = offset_from_bottom($last_row);

    return offset > 0;
}

export function offset_from_bottom($last_row: JQuery): number {
    // A positive return value here means the last row is
    // below the bottom of the feed (i.e. obscured by the compose
    // box or even further below the bottom).
    const message_bottom = $last_row.get_offset_to_window().bottom;
    const info = message_viewport_info();

    return message_bottom - info.visible_bottom;
}

export function set_message_position(
    message_top: number,
    message_height: number,
    viewport_info: MessageViewportInfo,
    ratio: number,
): void {
    // message_top = offset of the top of a message that you are positioning
    // message_height = height of the message that you are positioning
    // viewport_info = result of calling message_viewport.message_viewport_info
    // ratio = fraction indicating how far down the screen the msg should be

    let how_far_down_in_visible_page = viewport_info.visible_height * ratio;

    // special case: keep large messages fully on the screen
    if (how_far_down_in_visible_page + message_height > viewport_info.visible_height) {
        how_far_down_in_visible_page = viewport_info.visible_height - message_height;

        // Next handle truly gigantic messages.  We just say that the top of the
        // message goes to the top of the viewing area.  Realistically, gigantic
        // messages should either be condensed, socially frowned upon, or scrolled
        // with the mouse.
        if (how_far_down_in_visible_page < 0) {
            how_far_down_in_visible_page = 0;
        }
    }

    const hidden_top = viewport_info.visible_top - scrollTop();

    const message_offset = how_far_down_in_visible_page + hidden_top;

    const new_scroll_top = message_top - message_offset;

    message_scroll_state.set_update_selection_on_next_scroll(false);
    scrollTop(new_scroll_top);
}

function in_viewport_or_tall(
    rect: DOMRect,
    top_of_feed: number,
    bottom_of_feed: number,
    require_fully_visible: boolean,
): boolean {
    if (require_fully_visible) {
        return (
            rect.top > top_of_feed && // Message top is in view and
            (rect.bottom < bottom_of_feed || // message is fully in view or
                (rect.height > bottom_of_feed - top_of_feed && rect.top < bottom_of_feed))
        ); // message is tall.
    }
    return rect.bottom > top_of_feed && rect.top < bottom_of_feed;
}

function add_to_visible<T>(
    $candidates: JQuery,
    visible: T[],
    top_of_feed: number,
    bottom_of_feed: number,
    require_fully_visible: boolean,
    row_to_output: ($row: HTMLElement) => T,
): void {
    for (const row of $candidates) {
        const row_rect = row.getBoundingClientRect();
        // Mark very tall messages as read once we've gotten past them
        if (in_viewport_or_tall(row_rect, top_of_feed, bottom_of_feed, require_fully_visible)) {
            visible.push(row_to_output(row));
        } else {
            break;
        }
    }
}

const top_of_feed = new util.CachedValue({
    compute_value() {
        const $header = $("#navbar-fixed-container");
        let visible_top = $header.outerHeight() ?? 0;

        const $sticky_header = $(".sticky_header");
        if ($sticky_header.length) {
            visible_top += $sticky_header.outerHeight() ?? 0;
        }
        return visible_top;
    },
});

const bottom_of_feed = new util.CachedValue({
    compute_value() {
        return $("#compose")[0].getBoundingClientRect().top;
    },
});

function _visible_divs<T>(
    $selected_row: JQuery,
    row_min_height: number,
    row_to_output: ($row: HTMLElement) => T,
    div_class: string,
    require_fully_visible: boolean,
): T[] {
    // Note that when using getBoundingClientRect() we are getting offsets
    // relative to the visible window, but when using jQuery's offset() we are
    // getting offsets relative to the full scrollable window. You can't try to
    // compare heights from these two methods.
    const height = bottom_of_feed.get() - top_of_feed.get();
    const num_neighbors = Math.floor(height / row_min_height);

    // We do this explicitly without merges and without recalculating
    // the feed bounds to keep this computation as cheap as possible.
    const visible: T[] = [];
    const $above_pointer = $selected_row
        .prevAll(`div.${CSS.escape(div_class)}`)
        .slice(0, num_neighbors);
    const $below_pointer = $selected_row
        .nextAll(`div.${CSS.escape(div_class)}`)
        .slice(0, num_neighbors);
    add_to_visible(
        $selected_row,
        visible,
        top_of_feed.get(),
        bottom_of_feed.get(),
        require_fully_visible,
        row_to_output,
    );
    add_to_visible(
        $above_pointer,
        visible,
        top_of_feed.get(),
        bottom_of_feed.get(),
        require_fully_visible,
        row_to_output,
    );
    add_to_visible(
        $below_pointer,
        visible,
        top_of_feed.get(),
        bottom_of_feed.get(),
        require_fully_visible,
        row_to_output,
    );

    return visible;
}

export function visible_groups(require_fully_visible: boolean): HTMLElement[] {
    assert(message_lists.current !== undefined);
    const $selected_row = message_lists.current.selected_row();
    if ($selected_row === undefined || $selected_row.length === 0) {
        return [];
    }

    const $selected_group = rows.get_message_recipient_row($selected_row);

    function get_row(row: HTMLElement): HTMLElement {
        return row;
    }

    // Being simplistic about this, the smallest group is about 75 px high.
    return _visible_divs<HTMLElement>(
        $selected_group,
        75,
        get_row,
        "recipient_row",
        require_fully_visible,
    );
}

export function visible_messages(require_fully_visible: boolean): Message[] {
    assert(message_lists.current !== undefined);
    const $selected_row = message_lists.current.selected_row();

    function row_to_id(row: HTMLElement): Message {
        assert(message_lists.current !== undefined);
        return message_lists.current.get(rows.id($(row)))!;
    }

    // Being simplistic about this, the smallest message is 25 px high.
    return _visible_divs<Message>(
        $selected_row,
        25,
        row_to_id,
        "message_row",
        require_fully_visible,
    );
}

export function scrollTop(): number;
export function scrollTop(target_scrollTop: number): JQuery;
export function scrollTop(target_scrollTop?: number): JQuery | number {
    const orig_scrollTop = $scroll_container.scrollTop();
    if (target_scrollTop === undefined) {
        return orig_scrollTop ?? 0;
    }
    let $ret = $scroll_container.scrollTop(target_scrollTop);
    const new_scrollTop = $scroll_container.scrollTop();
    const space_to_scroll = $("#bottom_whitespace").get_offset_to_window().top - height();

    // Check whether our scrollTop didn't move even though one could have scrolled down
    if (
        space_to_scroll > 0 &&
        target_scrollTop > 0 &&
        orig_scrollTop === 0 &&
        new_scrollTop === 0
    ) {
        // Chrome has a bug where sometimes calling
        // window.scrollTop(x) has no effect, resulting in the browser
        // staying at 0 -- and afterwards if you call
        // window.scrollTop(x) again, it will still do nothing.  To
        // fix this, we need to first scroll to some other place.
        blueslip.info(
            "ScrollTop did nothing when scrolling to " + target_scrollTop + ", fixing...",
        );
        // First scroll to 1 in order to clear the stuck state
        $scroll_container.scrollTop(1);
        // And then scroll where we intended to scroll to
        $ret = $scroll_container.scrollTop(target_scrollTop);
        if ($scroll_container.scrollTop() === 0) {
            blueslip.info(
                "ScrollTop fix did not work when scrolling to " +
                    target_scrollTop +
                    "!  space_to_scroll was " +
                    space_to_scroll,
            );
        }
    }
    return $ret;
}

export function stop_auto_scrolling(): void {
    if (in_stoppable_autoscroll) {
        $scroll_container.stop();
    }
}

export function system_initiated_animate_scroll(
    scroll_amount: number,
    update_selection_on_scroll = false,
): void {
    message_scroll_state.set_update_selection_on_next_scroll(update_selection_on_scroll);
    const viewport_offset = scrollTop();
    in_stoppable_autoscroll = true;
    $scroll_container.animate({
        scrollTop: viewport_offset + scroll_amount,
        always() {
            in_stoppable_autoscroll = false;
        },
    });
}

export function user_initiated_animate_scroll(scroll_amount: number): void {
    message_scroll_state.set_update_selection_on_next_scroll(false);
    in_stoppable_autoscroll = false; // defensive

    const viewport_offset = scrollTop();

    $scroll_container.animate({
        scrollTop: viewport_offset + scroll_amount,
    });
}

export function recenter_view(
    $message: JQuery,
    {from_scroll = false, force_center = false} = {},
): void {
    // BarnOwl-style recentering: if the pointer is too high, move it to
    // the 1/2 marks. If the pointer is too low, move it to the 1/7 mark.
    // See keep_pointer_in_view() for related logic to keep the pointer onscreen.

    const viewport_info = message_viewport_info();
    const top_threshold = viewport_info.visible_top;

    const bottom_threshold = viewport_info.visible_bottom;

    const message_top = $message.get_offset_to_window().top;
    const message_height = $message.outerHeight(true) ?? 0;
    const message_bottom = message_top + message_height;

    const is_above = message_top < top_threshold;
    const is_below = message_bottom > bottom_threshold;

    if (from_scroll) {
        // If the message you're trying to center on is already in view AND
        // you're already trying to move in the direction of that message,
        // don't try to recenter. This avoids disorienting jumps when the
        // pointer has gotten itself outside the threshold (e.g. by
        // autoscrolling).
        if (is_above && last_movement_direction >= 0) {
            return;
        }
        if (is_below && last_movement_direction <= 0) {
            return;
        }
    }

    if (is_above || force_center) {
        set_message_position(message_top, message_height, viewport_info, 1 / 2);
    } else if (is_below) {
        set_message_position(message_top, message_height, viewport_info, 1 / 7);
    }
}

export function maybe_scroll_to_show_message_top(): void {
    assert(message_lists.current !== undefined);
    // Sets the top of the message to the top of the viewport.
    // Only applies if the top of the message is out of view above the visible area.
    const $selected_message = message_lists.current.selected_row();
    const viewport_info = message_viewport_info();
    const message_top = $selected_message.get_offset_to_window().top;
    const message_height = $selected_message.outerHeight(true) ?? 0;
    if (message_top < viewport_info.visible_top) {
        set_message_position(message_top, message_height, viewport_info, 0);
    }
}

export function is_message_below_viewport($message_row: JQuery): boolean {
    const info = message_viewport_info();
    const offset = $message_row.get_offset_to_window();
    return offset.top >= info.visible_bottom;
}

export function keep_pointer_in_view(): void {
    assert(message_lists.current !== undefined);
    // See message_viewport.recenter_view() for related logic to keep the pointer onscreen.
    // This function mostly comes into place for mouse scrollers, and it
    // keeps the pointer in view.  For people who purely scroll with the
    // mouse, the pointer is kind of meaningless to them, but keyboard
    // users will occasionally do big mouse scrolls, so this gives them
    // a pointer reasonably close to the middle of the screen.
    let $candidate;
    let $next_row = message_lists.current.selected_row();

    if ($next_row.length === 0) {
        return;
    }

    const info = message_viewport_info();
    const top_threshold = info.visible_top + (1 / 10) * info.visible_height;
    const bottom_threshold = info.visible_top + (9 / 10) * info.visible_height;

    function message_is_far_enough_down(): boolean {
        if (at_rendered_top()) {
            return true;
        }

        const message_top = $next_row.get_offset_to_window().top;

        // If the message starts after the very top of the screen, we just
        // leave it alone.  This avoids bugs like #1608, where overzealousness
        // about repositioning the pointer can cause users to miss messages.
        if (message_top >= info.visible_top) {
            return true;
        }

        // If at least part of the message is below top_threshold (10% from
        // the top), then we also leave it alone.
        const bottom_offset = message_top + ($next_row.outerHeight(true) ?? 0);
        if (bottom_offset >= top_threshold) {
            return true;
        }

        // If we got this far, the message is not "in view."
        return false;
    }

    function message_is_far_enough_up(): boolean {
        return at_rendered_bottom() || $next_row.get_offset_to_window().top <= bottom_threshold;
    }

    function adjust(
        in_view: () => boolean,
        get_next_row: ($message_row: JQuery) => JQuery,
    ): boolean {
        // return true only if we make an actual adjustment, so
        // that we know to short circuit the other direction
        if (in_view()) {
            return false; // try other side
        }
        while (!in_view()) {
            $candidate = get_next_row($next_row);
            if ($candidate.length === 0) {
                break;
            }
            $next_row = $candidate;
        }
        return true;
    }

    if (!adjust(message_is_far_enough_down, rows.next_visible)) {
        adjust(message_is_far_enough_up, rows.prev_visible);
    }

    message_lists.current.select_id(rows.id($next_row), {from_scroll: true});
}

export function scroll_to_selected(): void {
    assert(message_lists.current !== undefined);
    const $selected_row = message_lists.current.selected_row();
    if ($selected_row && $selected_row.length !== 0) {
        recenter_view($selected_row);
    }
}

export let scroll_to_selected_planned = false;

export function plan_scroll_to_selected(): void {
    scroll_to_selected_planned = true;
}

export function maybe_scroll_to_selected(): void {
    // If we have made a plan to scroll to the selected message but
    // deferred doing so, do so here.
    if (scroll_to_selected_planned) {
        scroll_to_selected();
        scroll_to_selected_planned = false;
    }
}

export function initialize(): void {
    // This handler must be placed before all resize handlers in our application
    $(window).on("resize", () => {
        cached_width.reset();
        cached_height.reset();
        top_of_feed.reset();
        bottom_of_feed.reset();
    });

    $(document).on("compose_started compose_canceled compose_finished", () => {
        bottom_of_feed.reset();
    });

    // We stop autoscrolling when the user is clearly in the middle of
    // doing something.  Be careful, though, if you try to capture
    // mousemove, then you will have to contend with the autoscroll
    // itself generating mousemove events.
    $(document).on("message_selected.zulip wheel", () => {
        stop_auto_scrolling();
    });
}
