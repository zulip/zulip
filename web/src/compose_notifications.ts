import $ from "jquery";
import assert from "minimalistic-assert";

import render_automatic_new_visibility_policy_banner from "../templates/compose_banner/automatic_new_visibility_policy_banner.hbs";
import render_message_sent_banner from "../templates/compose_banner/message_sent_banner.hbs";
import render_unmute_topic_banner from "../templates/compose_banner/unmute_topic_banner.hbs";

import * as blueslip from "./blueslip";
import * as compose_banner from "./compose_banner";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import type {Message} from "./message_store";
import * as narrow_state from "./narrow_state";
import * as people from "./people";
import * as stream_data from "./stream_data";
import * as user_topics from "./user_topics";

export function notify_unmute(muted_narrow: string, stream_id: number, topic_name: string): void {
    const $unmute_notification = $(
        render_unmute_topic_banner({
            muted_narrow,
            stream_id,
            topic_name,
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

export function notify_above_composebox(
    banner_text: string,
    classname: string,
    above_composebox_narrow_url: string | null,
    link_msg_id: number,
    link_text: string,
): void {
    const $notification = $(
        render_message_sent_banner({
            banner_text,
            classname,
            above_composebox_narrow_url,
            link_msg_id,
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
    const stream_topic = get_message_header(message);
    const narrow_url = get_above_composebox_narrow_url(message);
    const $notification = $(
        render_automatic_new_visibility_policy_banner({
            banner_type: compose_banner.SUCCESS,
            classname: compose_banner.CLASSNAMES.automatic_new_visibility_policy,
            link_msg_id: data.id,
            channel_topic: stream_topic,
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
function get_message_header(message: Message): string {
    if (message.type === "stream") {
        const stream_name = stream_data.get_stream_name_from_id(message.stream_id);
        return `#${stream_name} > ${message.topic}`;
    }
    if (message.display_recipient.length > 2) {
        return $t(
            {defaultMessage: "group direct messages with {recipient}"},
            {recipient: message.display_reply_to},
        );
    }
    if (people.is_current_user(message.reply_to)) {
        return $t({defaultMessage: "direct messages with yourself"});
    }
    return $t(
        {defaultMessage: "direct messages with {recipient}"},
        {recipient: message.display_reply_to},
    );
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

export function get_local_notify_mix_reason(message: Message): string | undefined {
    if (message_lists.current === undefined) {
        // For non-message list views like Inbox, the message is not visible after sending it.
        return undefined;
    }

    const $row = message_lists.current.get_row(message.id);
    if ($row.length > 0) {
        // If our message is in the current message list, we do
        // not have a mix, so we are happy.
        return undefined;
    }

    // offscreen because it is outside narrow
    // we can only look for these on non-search (can_apply_locally) messages
    // see also: exports.notify_messages_outside_current_search
    const current_filter = narrow_state.filter();
    if (
        current_filter &&
        current_filter.can_apply_locally() &&
        !current_filter.predicate()(message)
    ) {
        return $t({defaultMessage: "Sent! Your message is outside your current view."});
    }

    return undefined;
}

export function notify_local_mixes(messages: Message[], need_user_to_scroll: boolean): void {
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

        let banner_text = get_local_notify_mix_reason(message);

        const link_msg_id = message.id;

        if (!banner_text) {
            if (need_user_to_scroll) {
                banner_text = $t({defaultMessage: "Sent!"});
                const link_text = $t({defaultMessage: "Scroll down to view your message."});
                notify_above_composebox(
                    banner_text,
                    compose_banner.CLASSNAMES.sent_scroll_to_view,
                    // Don't display a URL on hover for the "Scroll to bottom" link.
                    null,
                    link_msg_id,
                    link_text,
                );
                compose_banner.set_scroll_to_message_banner_message_id(link_msg_id);
            }

            // This is the HAPPY PATH--for most messages we do nothing
            // other than maybe sending the above message.
            continue;
        }

        const link_text = $t(
            {defaultMessage: "Go to {message_recipient}"},
            {message_recipient: get_message_header(message)},
        );

        notify_above_composebox(
            banner_text,
            compose_banner.CLASSNAMES.narrow_to_recipient,
            get_above_composebox_narrow_url(message),
            link_msg_id,
            link_text,
        );
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
        if (!people.is_current_user(message.sender_email)) {
            continue;
        }
        const above_composebox_narrow_url = get_above_composebox_narrow_url(message);
        const link_text = $t(
            {defaultMessage: "Narrow to {message_recipient}"},
            {message_recipient: get_message_header(message)},
        );
        notify_above_composebox(
            $t({defaultMessage: "Sent! Your recent message is outside the current search."}),
            compose_banner.CLASSNAMES.narrow_to_recipient,
            above_composebox_narrow_url,
            message.id,
            link_text,
        );
    }
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
