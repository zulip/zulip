import $ from "jquery";
import assert from "minimalistic-assert";

import render_mark_as_read_disabled_banner from "../templates/unread_banner/mark_as_read_disabled_banner.hbs";
import render_mark_as_read_only_in_conversation_view from "../templates/unread_banner/mark_as_read_only_in_conversation_view.hbs";
import render_mark_as_read_turned_off_banner from "../templates/unread_banner/mark_as_read_turned_off_banner.hbs";

import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import * as narrow_state from "./narrow_state.ts";
import {web_mark_read_on_scroll_policy_values} from "./settings_config.ts";
import * as unread from "./unread.ts";
import type {FullUnreadCountsData} from "./unread.ts";
import {user_settings} from "./user_settings.ts";

let user_closed_unread_banner = false;

type UpdateUnreadCountsHook = (counts: FullUnreadCountsData, skip_animations: boolean) => void;
const update_unread_counts_hooks: UpdateUnreadCountsHook[] = [];

export function register_update_unread_counts_hook(f: UpdateUnreadCountsHook): void {
    update_unread_counts_hooks.push(f);
}

function set_mark_read_on_scroll_state_banner(banner_html: string): void {
    $("#mark_read_on_scroll_state_banner").html(banner_html);
    // This place holder is essential since hiding the unread banner would reduce
    // scrollable place, shifting the message list downward if the scrollbar is
    // at bottom.
    $("#mark_read_on_scroll_state_banner_place_holder").html(banner_html);
}

export function update_unread_banner(): void {
    if (message_lists.current === undefined) {
        return;
    }

    const filter = narrow_state.filter();
    const is_conversation_view = filter === undefined ? false : filter.is_conversation_view();
    toggle_dummy_banner(false);

    if (
        user_settings.web_mark_read_on_scroll_policy ===
        web_mark_read_on_scroll_policy_values.never.code
    ) {
        set_mark_read_on_scroll_state_banner(render_mark_as_read_disabled_banner());
    } else if (
        user_settings.web_mark_read_on_scroll_policy ===
            web_mark_read_on_scroll_policy_values.conversation_only.code &&
        !is_conversation_view
    ) {
        set_mark_read_on_scroll_state_banner(render_mark_as_read_only_in_conversation_view());
    } else {
        set_mark_read_on_scroll_state_banner(render_mark_as_read_turned_off_banner());
        if (message_lists.current.can_mark_messages_read_without_setting()) {
            hide_unread_banner();
        }
    }
}

function toggle_dummy_banner(state: boolean): void {
    $("#mark_read_on_scroll_state_banner_place_holder").toggleClass("hide", !state);
    $("#mark_read_on_scroll_state_banner_place_holder").toggleClass("invisible", state);
}

export function hide_unread_banner(): void {
    $("#mark_read_on_scroll_state_banner").toggleClass("hide", true);
    toggle_dummy_banner(true);
}

export function reset_unread_banner(): void {
    hide_unread_banner();
    user_closed_unread_banner = false;
}

export function notify_messages_remain_unread(): void {
    if (!user_closed_unread_banner) {
        $("#mark_read_on_scroll_state_banner").toggleClass("hide", false);
        toggle_dummy_banner(false);
    }
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
}

export function initialize({
    notify_server_messages_read,
}: {
    notify_server_messages_read: (unread_messages: Message[]) => void;
}): void {
    const skip_animations = true;
    update_unread_counts(skip_animations);
    $("body").on("click", "#mark_view_read", () => {
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

        hide_unread_banner();
    });
    $("body").on("click", "#mark_as_read_close", () => {
        hide_unread_banner();
        user_closed_unread_banner = true;
    });

    // The combination of these functions in sequence ensures we have
    // at least one copy of the unread banner in the DOM, invisible;
    // this somewhat strange pattern allows our CSS to reserve space for
    // the banner, to avoid scroll position jumps when it is shown/hidden.
    update_unread_banner();
    hide_unread_banner();
}
