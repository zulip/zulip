import {$} from "jquery";
import _ from "lodash";

import * as compose_banner from "./compose_banner.ts";
import * as message_fetch from "./message_fetch.ts";
import * as message_lists from "./message_lists.ts";
import * as message_scroll_state from "./message_scroll_state.ts";
import * as message_viewport from "./message_viewport.ts";
import * as narrow_state from "./narrow_state.ts";
import * as scroll_to_bottom_button from "./scroll_to_bottom_button.ts";
import * as unread from "./unread.ts";
import * as unread_ops from "./unread_ops.ts";
import * as unread_ui from "./unread_ui.ts";

export function scroll_finished(): void {
    message_scroll_state.set_actively_scrolling(false);
    // update() does nothing while actively_scrolling is set.
    scroll_to_bottom_button.update();

    if (message_lists.current === undefined) {
        return;
    }

    // It's possible that we are in transit and message_lists.current is not defined.
    // We still want the rest of the code to run but it's fine to skip this.
    message_lists.current.view.update_sticky_recipient_headers();

    if (compose_banner.scroll_to_message_banner_message_id !== null) {
        const $message_row = message_lists.current.get_row(
            compose_banner.scroll_to_message_banner_message_id,
        );
        if ($message_row.length > 0 && !message_viewport.is_message_below_viewport($message_row)) {
            compose_banner.clear_message_sent_banners(false);
        }
    }

    if (message_scroll_state.update_selection_on_next_scroll) {
        message_viewport.keep_pointer_in_view();
        // If we don't want to update message selection on this scroll,
        // we also don't want to mark any visible messages as read and
        // are waiting on user input to do so. So, we only mark messages
        // as read if we are updating selection on this scroll.
        //
        // For /near/ views, check whether we should resume marking
        // messages as read before processing visibility.
        message_lists.current.maybe_resume_reading_for_near_view();
        // When the window scrolls, it may cause some messages to
        // enter the screen and become read.  Calling
        // unread_ops.process_visible will update necessary
        // data structures and DOM elements.
        unread_ops.process_visible();
    } else {
        message_scroll_state.set_update_selection_on_next_scroll(true);
    }

    if (message_lists.current.view.should_fetch_older_messages()) {
        // Subtle note: While we've only checked that we're at the
        // very top of the render window (i.e. there may be some more
        // cached messages to render), it's a good idea to fetch
        // additional message history even if we're not actually at
        // the edge of what we already have from the server.
        message_fetch.maybe_load_older_messages({
            msg_list: message_lists.current,
            msg_list_data: message_lists.current.data,
        });
    }

    if (message_lists.current.view.should_fetch_newer_messages()) {
        // See the similar message_viewport.at_rendered_top block.
        message_fetch.maybe_load_newer_messages({
            msg_list: message_lists.current,
        });
    }
}

let scroll_timer: ReturnType<typeof setTimeout> | undefined;
function scroll_finish(): void {
    message_scroll_state.set_actively_scrolling(true);

    // Don't present the "scroll to bottom" widget if the current
    // scroll was triggered by the keyboard.
    if (!message_scroll_state.keyboard_triggered_current_scroll) {
        scroll_to_bottom_button.show_scroll_to_bottom_button();
    }
    message_scroll_state.set_keyboard_triggered_current_scroll(false);

    clearTimeout(scroll_timer);
    scroll_timer = setTimeout(scroll_finished, 100);
}

export function initialize(): void {
    $(document).on(
        "scroll",
        _.throttle(() => {
            if (message_lists.current === undefined) {
                // When in a non-message view, we don't need to process
                // message scroll events. We just hide the scroll-to-bottom
                // button instantly, if it is already visible.
                scroll_to_bottom_button.update();
                return;
            }

            message_lists.current.view.update_sticky_recipient_headers();
            scroll_finish();
        }, 50),
    );

    // Scroll handler that marks messages as read when you scroll past them.
    $(document).on("message_selected.zulip", (event) => {
        if (event.id === -1) {
            return;
        }

        if (event.mark_read && event.previously_selected_id !== -1) {
            // Mark messages between old pointer and new pointer as read
            if (event.id < event.previously_selected_id) {
                // We don't mark messages as read when the pointer moves up.
                return;
            }

            const messages = event.msg_list.message_range(event.previously_selected_id, event.id);
            // If the user just arrived at the message `event.id`, we don't mark it as read
            // unless it is the last message in the list.
            // We only mark messages as read when the pointer moves past the message.
            // This is likely the last message in the list. So, we loop through the messages
            // in reverse order to find the message.
            for (let i = messages.length - 1; i >= 0; i -= 1) {
                if (messages[i]!.id === event.id && event.id !== event.msg_list.last()?.id) {
                    messages.splice(i, 1);
                    break;
                }
            }

            if (event.msg_list.can_mark_messages_read()) {
                unread_ops.notify_server_messages_read(messages, {from: "pointer"});
            } else if (
                unread.get_unread_messages(messages).length > 0 &&
                // The below checks might seem redundant, but it's
                // possible this logic, which runs after a delay, lost
                // a race with switching to another view, like Recent
                // Topics, and we don't want to display this banner
                // in such a view.
                //
                // This can likely be fixed more cleanly with another approach.
                narrow_state.filter() !== undefined &&
                message_lists.current === event.msg_list
            ) {
                unread_ui.notify_messages_remain_unread();
            }
        }
    });
}
