import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";

import render_mark_as_read_button_tooltip from "../templates/mark_as_read_button_tooltip.hbs";
import render_message_list_navigation_buttons from "../templates/message_list_navigation_buttons.hbs";
import render_next_unread_conversation_tooltip from "../templates/next_unread_conversation_tooltip.hbs";

import * as browser_history from "./browser_history.ts";
import * as message_lists from "./message_lists.ts";
import * as narrow_state from "./narrow_state.ts";
import {web_mark_read_on_scroll_policy_values} from "./settings_config.ts";
import * as settings_config from "./settings_config.ts";
import * as tippyjs from "./tippyjs.ts";
import * as ui_util from "./ui_util.ts";
import * as unread from "./unread.ts";
import {user_settings} from "./user_settings.ts";

export function update_next_unread_conversation_button(): boolean {
    if (message_lists.current === undefined) {
        return false;
    }

    const filter = message_lists.current.data.filter;
    const $next_unread = $("#message-list-navigation-next-unread-conversation");
    if (
        (filter.can_show_next_unread_dm_conversation_button() &&
            unread.get_msg_ids_for_private().length > 0) ||
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

export function handle_right_arrow(): boolean {
    assert(document.activeElement !== null);
    const $focused_button = $(document.activeElement);
    let $next_button = $focused_button.nextAll(":visible").first();
    if ($next_button.length === 0) {
        $next_button = $focused_button.siblings(":visible").first();
    }

    if ($next_button[0] === $focused_button[0]) {
        return true;
    }

    $next_button.trigger("focus");
    return true;
}

export function render(): void {
    let home_view_code;
    switch (user_settings.web_home_view) {
        case settings_config.web_home_view_values.inbox.code:
            home_view_code = "inbox";
            break;
        case settings_config.web_home_view_values.all_messages.code:
            home_view_code = "all-messages";
            break;
        case settings_config.web_home_view_values.recent_topics.code:
            home_view_code = "recent";
            break;
    }

    const rendered_buttons = render_message_list_navigation_buttons({home_view_code});
    $("#message-list-navigation").html(rendered_buttons);
    update();
}

export function init(): void {
    render();
    $("body").on("click", "#message-list-navigation-home-view", (e) => {
        $(e.currentTarget).trigger("blur");
        browser_history.set_hash("");
        $(document).trigger(new $.Event("hashchange"));
    });

    tippy.delegate("body", {
        target: "#message-list-navigation-home-view",
        placement: "bottom",
        trigger: "mouseenter",
        delay: tippyjs.EXTRA_LONG_HOVER_DELAY,
        appendTo: () => document.body,
    });

    tippy.delegate("body", {
        target: "#message-list-navigation-next-unread-conversation",
        trigger: "mouseenter",
        delay: tippyjs.EXTRA_LONG_HOVER_DELAY,
        appendTo: () => document.body,
        placement: "bottom",
        onShow(instance) {
            assert(message_lists.current !== undefined);
            const is_unread_dm_conversation =
                message_lists.current.data.filter.contains_only_private_messages();
            instance.setContent(
                ui_util.parse_html(
                    render_next_unread_conversation_tooltip({is_unread_dm_conversation}),
                ),
            );
        },
    });

    tippy.delegate("body", {
        target: "#message-list-navigation-mark-as-read",
        trigger: "mouseenter",
        delay: tippyjs.EXTRA_LONG_HOVER_DELAY,
        appendTo: () => document.body,
        placement: "bottom",
        onShow(instance) {
            const cannot_read_due_to_settings =
                user_settings.web_mark_read_on_scroll_policy !==
                web_mark_read_on_scroll_policy_values.always.code;
            instance.setContent(
                ui_util.parse_html(
                    render_mark_as_read_button_tooltip({cannot_read_due_to_settings}),
                ),
            );
        },
    });
}
