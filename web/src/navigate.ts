import assert from "minimalistic-assert";

import * as message_lists from "./message_lists.ts";
import * as message_view from "./message_view.ts";
import * as message_viewport from "./message_viewport.ts";
import * as unread_ops from "./unread_ops.ts";

function go_to_row(msg_id: number): void {
    assert(message_lists.current !== undefined);
    message_lists.current.select_id(msg_id, {then_scroll: true, from_scroll: true});
}

export function up(): void {
    assert(message_lists.current !== undefined);
    message_viewport.set_last_movement_direction(-1);
    const msg_id = message_lists.current.prev();
    if (msg_id === undefined) {
        return;
    }
    go_to_row(msg_id);
}

export function down(with_centering = false): void {
    assert(message_lists.current !== undefined);
    message_viewport.set_last_movement_direction(1);

    if (message_lists.current.is_at_end()) {
        if (with_centering) {
            // At the last message, scroll to the bottom so we have
            // lots of nice whitespace for new messages coming in.
            const $current_msg_list = message_lists.current.view.$list;
            message_viewport.scrollTop(
                ($current_msg_list.outerHeight(true) ?? 0) - message_viewport.height() * 0.1,
            );
            unread_ops.process_visible();
        }

        return;
    }

    // Normal path starts here.
    const msg_id = message_lists.current.next();
    if (msg_id === undefined) {
        return;
    }
    go_to_row(msg_id);
}

export function to_home(): void {
    message_view.fast_track_current_msg_list_to_anchor("oldest");
}

export function to_end(): void {
    message_view.fast_track_current_msg_list_to_anchor("newest");
}

function amount_to_paginate(): number {
    // Some day we might have separate versions of this function
    // for Page Up vs. Page Down, but for now it's the same
    // strategy in either direction.
    const info = message_viewport.message_viewport_info();
    const page_size = info.visible_height;

    // We don't want to page up a full page, because Zulip users
    // are especially worried about missing messages, so we want
    // a little bit of the old page to stay on the screen.  The
    // value chosen here is roughly 2 or 3 lines of text, but there
    // is nothing sacred about it, and somebody more anal than we
    // might wish to tie this to the size of some particular DOM
    // element.
    const overlap_amount = 55;

    let delta = page_size - overlap_amount;

    // If the user has shrunk their browser a whole lot, pagination
    // is not going to be very pleasant, but we can at least
    // ensure they go in the right direction.
    if (delta < 1) {
        delta = 1;
    }

    return delta;
}

export function page_up_the_right_amount(): void {
    // This function's job is to scroll up the right amount,
    // after the user hits Page Up.  We do this ourselves
    // because we can't rely on the browser to account for certain
    // page elements, like the compose box, that sit in fixed
    // positions above the message pane.  For other scrolling
    // related adjustments, try to make those happen in the
    // scroll handlers, not here.
    const delta = amount_to_paginate();
    message_viewport.scrollTop(message_viewport.scrollTop() - delta);
}

export function page_down_the_right_amount(): void {
    // see also: page_up_the_right_amount
    const delta = amount_to_paginate();
    message_viewport.scrollTop(message_viewport.scrollTop() + delta);
}

export function page_up(): void {
    assert(message_lists.current !== undefined);
    if (message_viewport.at_rendered_top() && !message_lists.current.visibly_empty()) {
        if (message_lists.current.view.is_fetched_start_rendered()) {
            const first_message = message_lists.current.first();
            assert(first_message !== undefined);
            message_lists.current.select_id(first_message.id, {then_scroll: false});
        } else {
            const first_rendered_message = message_lists.current.view.first_rendered_message();
            assert(first_rendered_message !== undefined);
            message_lists.current.select_id(first_rendered_message.id, {
                then_scroll: false,
            });
        }
    } else {
        page_up_the_right_amount();
    }
}

export function page_down(): void {
    assert(message_lists.current !== undefined);
    if (message_viewport.at_rendered_bottom() && !message_lists.current.visibly_empty()) {
        if (message_lists.current.view.is_fetched_end_rendered()) {
            const last_message = message_lists.current.last();
            assert(last_message !== undefined);
            message_lists.current.select_id(last_message.id, {then_scroll: false});
        } else {
            const last_rendered_message = message_lists.current.view.last_rendered_message();
            assert(last_rendered_message !== undefined);
            message_lists.current.select_id(last_rendered_message.id, {
                then_scroll: false,
            });
        }
        unread_ops.process_visible();
    } else {
        page_down_the_right_amount();
    }
}
