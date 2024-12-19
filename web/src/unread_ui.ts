import $ from "jquery";
import assert from "minimalistic-assert";

import * as message_list_navigation from "./message_list_navigation.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import {page_params} from "./page_params.ts";
import * as unread from "./unread.ts";
import type {FullUnreadCountsData} from "./unread.ts";

type UpdateUnreadCountsHook = (counts: FullUnreadCountsData, skip_animations: boolean) => void;
const update_unread_counts_hooks: UpdateUnreadCountsHook[] = [];

export function register_update_unread_counts_hook(f: UpdateUnreadCountsHook): void {
    update_unread_counts_hooks.push(f);
}

export function set_count_toggle_button($elem: JQuery, count: number): JQuery {
    if (count === 0) {
        return $elem.hide();
    }
    return $elem.show();
}

export function update_unread_counts(skip_animations = false): void {
    // Pure computation:
    const res = unread.get_counts();

    // Side effects from here down:
    // This updates some DOM elements directly, so try to
    // avoid excessive calls to this.
    // See `ui_init.initialize_unread_ui` for the registered hooks.
    for (const hook of update_unread_counts_hooks) {
        hook(res, skip_animations);
    }

    // Set the unread indicator on the toggle for the left sidebar
    set_count_toggle_button($(".left-sidebar-toggle-unreadcount"), res.home_unread_messages);

    // Check if we should still display the next unread conversation button.
    message_list_navigation.update();
}

export function should_display_bankruptcy_banner(): boolean {
    // Until we've handled possibly declaring bankruptcy, don't show
    // unread counts since they only consider messages that are loaded
    // client side and may be different from the numbers reported by
    // the server.

    if (!page_params.furthest_read_time) {
        // We've never read a message.
        return false;
    }

    const now = Date.now() / 1000;
    if (
        unread.get_unread_message_count() > 500 &&
        now - page_params.furthest_read_time > 60 * 60 * 24 * 2
    ) {
        // 2 days.
        return true;
    }

    return false;
}

export function initialize({
    notify_server_messages_read,
}: {
    notify_server_messages_read: (unread_messages: Message[]) => void;
}): void {
    const skip_animations = true;
    update_unread_counts(skip_animations);

    $("body").on("click", "#message-list-navigation-mark-as-read", () => {
        assert(message_lists.current !== undefined);
        // Mark all messages in the current view as read.
        //
        // BUG: This logic only supports marking messages visible in
        // the present view as read; we need a server API to mark
        // every message matching the current search as read.
        const unread_messages = message_lists.current.data
            .all_messages()
            .filter((message) => message.unread);
        notify_server_messages_read(unread_messages);
        // New messages received may be marked as read based on narrow type.
        message_lists.current.resume_reading();
        // Hide the button after it's clicked.
        message_list_navigation.update();
        // Focus the next button or blur if no button is visible.
        message_list_navigation.handle_right_arrow();
    });
}
