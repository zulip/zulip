import $ from "jquery";
import assert from "minimalistic-assert";

import render_automatic_new_visibility_policy_banner from "../templates/compose_banner/automatic_new_visibility_policy_banner.hbs";
import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";
import render_jump_to_sent_message_conversation_banner from "../templates/compose_banner/jump_to_sent_message_conversation_banner.hbs";
import render_message_sent_banner from "../templates/compose_banner/message_sent_banner.hbs";
import render_unmute_topic_banner from "../templates/compose_banner/unmute_topic_banner.hbs";

import * as blueslip from "./blueslip.ts";
import * as compose_banner from "./compose_banner.ts";
import * as hash_util from "./hash_util.ts";
import {$t} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import * as narrow_state from "./narrow_state.ts";
import * as onboarding_steps from "./onboarding_steps.ts";
import * as people from "./people.ts";
import * as stream_data from "./stream_data.ts";
import {user_settings} from "./user_settings.ts";
import * as user_topics from "./user_topics.ts";
import * as util from "./util.ts";

export function notify_unmute(muted_narrow: string, stream_id: number, topic_name: string): void {
    const $unmute_notification = $(
        render_unmute_topic_banner({
            muted_narrow,
            stream_id,
            topic_name,
            is_empty_string_topic: topic_name === "",
            classname: compose_banner.CLASSNAMES.unmute_topic_notification,
            banner_type: "",
            button_text: $t({defaultMessage: "Unmute topic"}),
        }),
    );
    compose_banner.clear_unmute_topic_notifications();
    compose_banner.append_compose_banner_to_banner_list(
        $unmute_notification,
        $("#compose_banners"),
    );
}

type MessageRecipient =
    | {
          message_type: "channel";
          channel_name: string;
          topic_name: string;
          topic_display_name: string;
          is_empty_string_topic: boolean;
      }
    | {
          message_type: "direct";
          recipient_text: string;
      };

export function notify_above_composebox(
    banner_text: string,
    classname: string,
    above_composebox_narrow_url: string | null,
    link_msg_id: number,
    message_recipient: MessageRecipient | null,
    link_text: string | null,
): void {
    const $notification = $(
        render_message_sent_banner({
            banner_text,
            classname,
            above_composebox_narrow_url,
            link_msg_id,
            message_recipient,
            link_text,
        }),
    );
    // We pass in include_unmute_banner as false because we don't want to
    // clear any unmute_banner associated with this same message.
    compose_banner.clear_message_sent_banners(false);
    compose_banner.append_compose_banner_to_banner_list($notification, $("#compose_banners"));
}

export function notify_automatic_new_visibility_policy(
    message: Message,
    data: {automatic_new_visibility_policy: number; id: number},
): void {
    const followed =
        data.automatic_new_visibility_policy === user_topics.all_visibility_policies.FOLLOWED;
    const narrow_url = get_above_composebox_narrow_url(message);
    const message_recipient = get_message_recipient(message);
    assert(message_recipient.message_type === "channel");
    const $notification = $(
        render_automatic_new_visibility_policy_banner({
            banner_type: compose_banner.SUCCESS,
            classname: compose_banner.CLASSNAMES.automatic_new_visibility_policy,
            link_msg_id: data.id,
            channel_name: message_recipient.channel_name,
            // The base compose_banner.hbs expects a data-topic-name.
            topic_name: message_recipient.topic_name,
            topic_display_name: message_recipient.topic_display_name,
            is_empty_string_topic: message_recipient.is_empty_string_topic,
            narrow_url,
            followed,
            button_text: $t({defaultMessage: "Change setting"}),
            hide_close_button: true,
            is_onboarding_banner: true,
        }),
    );
    compose_banner.append_compose_banner_to_banner_list($notification, $("#compose_banners"));
}

// Note that this returns values that are not HTML-escaped, for use in
// Handlebars templates that will do further escaping.
function get_message_recipient(message: Message): MessageRecipient {
    if (message.type === "stream") {
        const channel_message_recipient: MessageRecipient = {
            message_type: "channel",
            channel_name: stream_data.get_stream_name_from_id(message.stream_id),
            topic_name: message.topic,
            topic_display_name: util.get_final_topic_display_name(message.topic),
            is_empty_string_topic: message.topic === "",
        };
        return channel_message_recipient;
    }

    // Only the stream format uses a string for this.
    assert(typeof message.display_recipient !== "string");
    const direct_message_recipient: MessageRecipient = {
        message_type: "direct",
        recipient_text: "",
    };
    if (message.display_recipient.length > 2) {
        direct_message_recipient.recipient_text = $t(
            {defaultMessage: "group direct messages with {recipient}"},
            {recipient: message.display_reply_to},
        );
        return direct_message_recipient;
    }
    if (
        message.display_recipient.length === 1 &&
        people.is_my_user_id(util.the(message.display_recipient).id)
    ) {
        direct_message_recipient.recipient_text = $t({
            defaultMessage: "direct messages with yourself",
        });
        return direct_message_recipient;
    }
    direct_message_recipient.recipient_text = $t(
        {defaultMessage: "direct messages with {recipient}"},
        {recipient: message.display_reply_to},
    );
    return direct_message_recipient;
}

export function get_muted_narrow(message: Message): string | undefined {
    if (
        message.type === "stream" &&
        stream_data.is_muted(message.stream_id) &&
        !user_topics.is_topic_unmuted_or_followed(message.stream_id, message.topic)
    ) {
        return "stream";
    }
    if (message.type === "stream" && user_topics.is_topic_muted(message.stream_id, message.topic)) {
        return "topic";
    }
    return undefined;
}

export function should_jump_to_sent_message_conversation(message: Message): boolean {
    if (!user_settings.web_navigate_to_sent_message) {
        return false;
    }

    if (message_lists.current === undefined) {
        // Non-message list views like Inbox.
        return true;
    }

    const current_filter = narrow_state.filter();
    const is_conversation_view =
        current_filter === undefined
            ? false
            : current_filter.is_conversation_view() ||
              current_filter.is_conversation_view_with_near();
    const $row = message_lists.current.get_row(message.id);
    if (is_conversation_view && $row.length > 0) {
        // If our message is in the current conversation view, we do
        // not have a mix, so we are happy.
        return false;
    }

    return true;
}

function should_show_narrow_to_recipient_banner(message: Message): boolean {
    if (user_settings.web_navigate_to_sent_message) {
        return false;
    }

    if (message_lists.current === undefined) {
        // Non-message list views like Inbox.
        return false;
    }

    const $row = message_lists.current.get_row(message.id);
    if ($row.length > 0) {
        // Our message is in the current message list.
        return false;
    }

    // offscreen because it is outside narrow
    // we can only look for these on non-search (can_apply_locally) messages
    // see also: notify_messages_outside_current_search
    const current_filter = narrow_state.filter();
    if (
        current_filter &&
        current_filter.can_apply_locally() &&
        !current_filter.predicate()(message)
    ) {
        return true;
    }

    return false;
}

export function notify_local_mixes(
    messages: Message[],
    need_user_to_scroll: boolean,
    {narrow_to_recipient}: {narrow_to_recipient: (message_id: number) => void},
): void {
    /*
        This code should only be called when we are displaying
        messages sent by current client. It notifies users that
        their messages aren't actually in the view that they
        composed to.

        This code is called after we insert messages into our
        message list widgets. All of the conditions here are
        checkable locally, so we may want to execute this code
        earlier in the codepath at some point and possibly punt
        on local rendering.

        Possible cleanup: Arguably, we should call this function
        unconditionally and just check if message.local_id is in
        sent_messages.messages here.
    */

    for (const message of messages) {
        if (!people.is_my_user_id(message.sender_id)) {
            // This can happen if the client is offline for a while
            // around the time this client sends a message; see the
            // caller of message_events.insert_new_messages.
            blueslip.info(
                "Slightly unexpected: A message not sent by us batches with those that were.",
            );
            continue;
        }

        const jump_to_sent_message_conversation = should_jump_to_sent_message_conversation(message);
        const show_narrow_to_recipient_banner = should_show_narrow_to_recipient_banner(message);

        const link_msg_id = message.id;

        if (!jump_to_sent_message_conversation && !show_narrow_to_recipient_banner) {
            if (need_user_to_scroll) {
                const banner_text = $t({defaultMessage: "Sent!"});
                const link_text = $t({defaultMessage: "Scroll down to view your message."});
                notify_above_composebox(
                    banner_text,
                    compose_banner.CLASSNAMES.sent_scroll_to_view,
                    // Don't display a URL on hover for the "Scroll to bottom" link.
                    null,
                    link_msg_id,
                    null,
                    link_text,
                );
                compose_banner.set_scroll_to_message_banner_message_id(link_msg_id);
            }

            // This is the HAPPY PATH--for most messages we do nothing
            // other than maybe sending the above message.
            continue;
        }

        if (show_narrow_to_recipient_banner) {
            const banner_text = $t({
                defaultMessage: "Sent! Your message is outside your current view.",
            });
            notify_above_composebox(
                banner_text,
                compose_banner.CLASSNAMES.narrow_to_recipient,
                get_above_composebox_narrow_url(message),
                link_msg_id,
                get_message_recipient(message),
                null,
            );
            continue;
        }

        narrow_to_recipient(link_msg_id);

        if (onboarding_steps.ONE_TIME_NOTICES_TO_DISPLAY.has("jump_to_conversation_banner")) {
            const new_row_html = render_jump_to_sent_message_conversation_banner({
                banner_type: compose_banner.SUCCESS,
                classname: compose_banner.CLASSNAMES.jump_to_sent_message_conversation,
                hide_close_button: true,
                is_onboarding_banner: true,
            });
            compose_banner.append_compose_banner_to_banner_list(
                $(new_row_html),
                $("#compose_banners"),
            );
        }
    }
}

function get_above_composebox_narrow_url(message: Message): string {
    let above_composebox_narrow_url;
    if (message.type === "stream") {
        above_composebox_narrow_url = hash_util.by_stream_topic_url(
            message.stream_id,
            message.topic,
        );
    } else {
        above_composebox_narrow_url = message.pm_with_url;
    }
    return above_composebox_narrow_url;
}

// for callback when we have to check with the server if a message should be in
// the message_lists.current (!can_apply_locally; a.k.a. "a search").
export function notify_messages_outside_current_search(messages: Message[]): void {
    for (const message of messages) {
        if (!people.is_my_user_id(message.sender_id)) {
            continue;
        }
        const above_composebox_narrow_url = get_above_composebox_narrow_url(message);
        notify_above_composebox(
            $t({defaultMessage: "Sent! Your message is outside your current view."}),
            compose_banner.CLASSNAMES.narrow_to_recipient,
            above_composebox_narrow_url,
            message.id,
            get_message_recipient(message),
            null,
        );
    }
}

export function maybe_show_one_time_non_interleaved_view_messages_fading_banner(): void {
    // Remove message fading banners if exists. Helps in live-updating banner.
    compose_banner.clear_non_interleaved_view_messages_fading_banner();
    compose_banner.clear_interleaved_view_messages_fading_banner();

    if (!onboarding_steps.ONE_TIME_NOTICES_TO_DISPLAY.has("non_interleaved_view_messages_fading")) {
        return;
    }

    // Wait to display the banner the first time until there's actually fading.
    const faded_messages_exist = $(".focused-message-list .recipient_row").hasClass("message-fade");
    if (!faded_messages_exist) {
        return;
    }

    const context = {
        banner_type: compose_banner.INFO,
        classname: compose_banner.CLASSNAMES.non_interleaved_view_messages_fading,
        banner_text: $t({
            defaultMessage:
                "Messages in your view are faded to remind you that you are viewing a different conversation from the one you are composing to.",
        }),
        button_text: $t({defaultMessage: "Got it"}),
        hide_close_button: true,
    };
    const new_row_html = render_compose_banner(context);

    compose_banner.append_compose_banner_to_banner_list($(new_row_html), $("#compose_banners"));
}

export function maybe_show_one_time_interleaved_view_messages_fading_banner(): void {
    // Remove message fading banners if exists. Helps in live-updating banner.
    compose_banner.clear_non_interleaved_view_messages_fading_banner();
    compose_banner.clear_interleaved_view_messages_fading_banner();

    if (!onboarding_steps.ONE_TIME_NOTICES_TO_DISPLAY.has("interleaved_view_messages_fading")) {
        return;
    }

    // Wait to display the banner the first time until there's actually fading.
    const faded_messages_exist = $(".focused-message-list .recipient_row").hasClass("message-fade");
    if (!faded_messages_exist) {
        return;
    }

    // TODO: Introduce two variants of the banner_text depending on whether
    // sending a message to the current recipient would appear in the view you're in.
    // See: https://github.com/zulip/zulip/pull/29634#issuecomment-2073274029
    const context = {
        banner_type: compose_banner.INFO,
        classname: compose_banner.CLASSNAMES.interleaved_view_messages_fading,
        banner_text: $t({
            defaultMessage:
                "To make it easier to tell where your message will be sent, messages in conversations you are not composing to are faded.",
        }),
        button_text: $t({defaultMessage: "Got it"}),
        hide_close_button: true,
    };
    const new_row_html = render_compose_banner(context);

    compose_banner.append_compose_banner_to_banner_list($(new_row_html), $("#compose_banners"));
}

export function reify_message_id(opts: {old_id: number; new_id: number}): void {
    const old_id = opts.old_id;
    const new_id = opts.new_id;

    // If a message ID that we're currently storing (as a link) has changed,
    // update that link as well
    for (const e of $("#compose_banners a")) {
        const $elem = $(e);
        const message_id = Number($elem.attr("data-message-id"));

        if (message_id === old_id) {
            $elem.attr("data-message-id", new_id);
            compose_banner.set_scroll_to_message_banner_message_id(new_id);
        }
    }
}

export function initialize(opts: {
    on_click_scroll_to_selected: () => void;
    on_narrow_to_recipient: (message_id: number) => void;
}): void {
    const {on_click_scroll_to_selected, on_narrow_to_recipient} = opts;
    $("#compose_banners").on(
        "click",
        ".narrow_to_recipient .above_compose_banner_action_link, .automatic_new_visibility_policy .above_compose_banner_action_link",
        (e) => {
            const message_id = Number($(e.currentTarget).attr("data-message-id"));
            on_narrow_to_recipient(message_id);
            e.stopPropagation();
            e.preventDefault();
        },
    );
    $("#compose_banners").on(
        "click",
        ".sent_scroll_to_view .above_compose_banner_action_link",
        (e) => {
            assert(message_lists.current !== undefined);
            const message_id = Number($(e.currentTarget).attr("data-message-id"));
            message_lists.current.select_id(message_id);
            on_click_scroll_to_selected();
            compose_banner.clear_message_sent_banners(false);
            e.stopPropagation();
            e.preventDefault();
        },
    );
}
