import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import * as browser_history from "./browser_history";
import * as message_lists from "./message_lists";
import * as narrow_state from "./narrow_state";
import {web_mark_read_on_scroll_policy_values} from "./settings_config";
import * as unread from "./unread";
import {user_settings} from "./user_settings";

let last_clicked_home_view_button = false;

export function update_next_unread_conversation_button(): boolean {
    if (message_lists.current === undefined) {
        return false;
    }

    const filter = message_lists.current.data.filter;
    const $next_unread = $("#message-list-navigation-next-unread-conversation");
    if (
        (filter.can_show_next_unread_dm_conversation_button() &&
            unread.get_msg_ids_for_private().length !== 0) ||
        (filter.can_show_next_unread_topic_conversation_button() &&
            unread.get_unread_topics().stream_unread_messages !== 0)
    ) {
        $next_unread.show();
        return true;
    }
    $next_unread.hide();
    return false;
}

export function update_mark_as_read_button(): boolean {
    if (message_lists.current === undefined) {
        return false;
    }

    const $mark_as_read = $("#message-list-navigation-mark-as-read");

    if (!message_lists.current.has_unread_messages()) {
        $mark_as_read.hide();
        return false;
    }

    const filter = narrow_state.filter();
    const is_conversation_view = filter === undefined ? false : filter.is_conversation_view();
    const msg_list_navigation_mark_as_read: tippy.ReferenceElement | undefined =
        $mark_as_read.get(0);
    assert(msg_list_navigation_mark_as_read !== undefined);

    if (
        user_settings.web_mark_read_on_scroll_policy ===
        web_mark_read_on_scroll_policy_values.never.code
    ) {
        $mark_as_read.show();
        return true;
    }

    if (
        user_settings.web_mark_read_on_scroll_policy ===
            web_mark_read_on_scroll_policy_values.conversation_only.code &&
        !is_conversation_view
    ) {
        $mark_as_read.show();
        return true;
    }

    if (message_lists.current.can_mark_messages_read_without_setting()) {
        $mark_as_read.hide();
        return false;
    }

    $mark_as_read.show();
    return true;
}

export function update_home_view_button(): boolean {
    const $home_view_button = $("#message-list-navigation-home-view");
    if (browser_history.is_current_hash_home_view()) {
        $home_view_button.hide();
        return false;
    }
    $home_view_button.show();
    return true;
}

export function update(): void {
    if (message_lists.current === undefined) {
        return;
    }

    if (message_lists.current.visibly_empty()) {
        message_lists.current.hide_navigation_bar();
        return;
    }

    const update_button_functions = [
        update_home_view_button,
        update_mark_as_read_button,
        update_next_unread_conversation_button,
    ];

    let any_button_visible = false;
    for (const update_function of update_button_functions) {
        if (update_function()) {
            any_button_visible = true;
        }
    }

    if (any_button_visible) {
        message_lists.current.show_navigation_bar();
    } else {
        message_lists.current.hide_navigation_bar();
    }
}

export function is_any_button_focused(): boolean {
    return document.activeElement?.classList.contains("message-list-navigation-button") ?? false;
}

export function handle_left_arrow(): boolean {
    assert(document.activeElement !== null);

    const $focused_button = $(document.activeElement);
    const $prev_button = $focused_button.prevAll(":visible").first();

    if ($prev_button.length === 0) {
        $focused_button.trigger("blur");
    } else {
        $prev_button.trigger("focus");
    }

    return true;
}

export function handle_right_arrow(): boolean {
    if (!is_any_button_focused()) {
        if ($("#message-list-navigation-mark-as-read:visible").length !== 0) {
            $("#message-list-navigation-mark-as-read").trigger("focus");
        } else if (
            $("#message-list-navigation-home-view:visible") &&
            last_clicked_home_view_button
        ) {
            $("#message-list-navigation-home-view").trigger("focus");
        } else {
            $("#message-list-navigation-next-unread-conversation").trigger("focus");
        }
        return true;
    }
    assert(document.activeElement !== null);

    const $focused_button = $(document.activeElement);
    const $next_button = $focused_button.nextAll(":visible").first();
    if ($next_button.length === 0) {
        $focused_button.trigger("blur");
    } else {
        $next_button.trigger("focus");
    }

    return true;
}

export function init(): void {
    $("#message-list-navigation-home-view").on("click", (e) => {
        last_clicked_home_view_button = true;
        e.currentTarget.blur();
        browser_history.set_hash("");
        $(document).trigger(new $.Event("hashchange"));
    });

    $("#message-list-navigation-next-unread-conversation").on("click", () => {
        last_clicked_home_view_button = false;
    });
}
