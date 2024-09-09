import $ from "jquery";

import * as alert_words from "./alert_words";
import * as blueslip from "./blueslip";
import * as desktop_notifications from "./desktop_notifications";
import {$t} from "./i18n";
import * as message_parser from "./message_parser";
import * as message_view from "./message_view";
import * as people from "./people";
import * as spoilers from "./spoilers";
import * as stream_data from "./stream_data";
import * as ui_util from "./ui_util";
import * as unread from "./unread";
import {user_settings} from "./user_settings";
import * as user_topics from "./user_topics";
import * as util from "./util";

function get_notification_content(message) {
    let content;
    // Convert the content to plain text, replacing emoji with their alt text
    const $content = $("<div>").html(message.content);
    ui_util.replace_emoji_with_text($content);
    ui_util.change_katex_to_raw_latex($content);
    ui_util.potentially_collapse_quotes($content);
    spoilers.hide_spoilers_in_notification($content);

    if (
        $content.text().trim() === "" &&
        (message_parser.message_has_image(message.content) ||
            message_parser.message_has_attachment(message.content))
    ) {
        content = $t({defaultMessage: "(attached file)"});
    } else {
        content = $content.text();
    }

    if (message.is_me_message) {
        content = message.sender_full_name + content.slice(3);
    }

    if (
        (message.type === "private" || message.type === "test-notification") &&
        !user_settings.pm_content_in_desktop_notifications
    ) {
        content = $t(
            {defaultMessage: "New direct message from {sender_full_name}"},
            {sender_full_name: message.sender_full_name},
        );
    }

    return content;
}

function debug_notification_source_value(message) {
    let notification_source;

    if (message.type === "private" || message.type === "test-notification") {
        notification_source = "pm";
    } else if (message.mentioned) {
        notification_source = "mention";
    } else if (message.alerted) {
        notification_source = "alert";
    } else {
        notification_source = "stream";
    }

    blueslip.debug("Desktop notification from source " + notification_source);
}

function get_notification_key(message) {
    let key;

    if (message.type === "private" || message.type === "test-notification") {
        key = message.display_reply_to;
    } else {
        const stream_name = stream_data.get_stream_name_from_id(message.stream_id);
        key = message.sender_full_name + " to " + stream_name + " > " + message.topic;
    }

    return key;
}

function remove_sender_from_list_of_recipients(message) {
    return `, ${message.display_reply_to}, `
        .replace(`, ${message.sender_full_name}, `, ", ")
        .slice(", ".length, -", ".length);
}

function get_notification_title(message, msg_count) {
    let title_prefix = message.sender_full_name;
    let title_suffix = "";
    let other_recipients;
    let other_recipients_translated;

    if (msg_count > 1) {
        title_prefix = $t(
            {defaultMessage: "{msg_count} messages from {sender_name}"},
            {msg_count, sender_name: message.sender_full_name},
        );
    }

    switch (message.type) {
        case "private":
            if (message.display_recipient.length > 2) {
                other_recipients = remove_sender_from_list_of_recipients(message);
                // Same as compose_ui.compute_placeholder_text.
                other_recipients_translated = util.format_array_as_list(
                    other_recipients.split(", "),
                    "long",
                    "conjunction",
                );
                // Character limit taken from https://www.pushengage.com/push-notification-character-limits
                // We use a higher character limit so that the 3rd sender can at least be partially visible so that
                // the user can distinguish the group DM.
                // If the message has too many recipients to list them all...
                if (title_prefix.length + other_recipients_translated.length > 50) {
                    // Then count how many people are in the conversation and summarize
                    title_suffix = $t(
                        {defaultMessage: "(to you and {participants_count} more)"},
                        {participants_count: message.display_recipient.length - 2},
                    );
                } else {
                    title_suffix = $t(
                        {defaultMessage: "(to you and {other_participant_names})"},
                        {other_participant_names: other_recipients_translated},
                    );
                }
            } else {
                title_suffix = $t({defaultMessage: "(to you)"});
            }

            return title_prefix + " " + title_suffix;
        case "stream": {
            const stream_name = stream_data.get_stream_name_from_id(message.stream_id);
            title_suffix = " (#" + stream_name + " > " + message.topic + ")";
            break;
        }
    }

    return title_prefix + title_suffix;
}

export function process_notification(notification) {
    const message = notification.message;
    const content = get_notification_content(message);
    const key = get_notification_key(message);
    let notification_object;
    let msg_count = 1;

    debug_notification_source_value(message);

    if (desktop_notifications.notice_memory.has(key)) {
        msg_count = desktop_notifications.notice_memory.get(key).msg_count + 1;
        notification_object = desktop_notifications.notice_memory.get(key).obj;
        notification_object.close();
    }

    const title = get_notification_title(message, msg_count);

    if (notification.desktop_notify) {
        const icon_url = people.small_avatar_url(message);
        notification_object = new desktop_notifications.NotificationAPI(title, {
            icon: icon_url,
            body: content,
            tag: message.id,
        });
        desktop_notifications.notice_memory.set(key, {
            obj: notification_object,
            msg_count,
            message_id: message.id,
        });

        if (typeof notification_object.addEventListener === "function") {
            // Sadly, some third-party Electron apps like Franz/Ferdi
            // misimplement the Notification API not inheriting from
            // EventTarget.  This results in addEventListener being
            // unavailable for them.
            notification_object.addEventListener("click", () => {
                notification_object.close();
                if (message.type !== "test-notification") {
                    message_view.narrow_by_topic(message.id, {trigger: "notification"});
                }
                window.focus();
            });
            notification_object.addEventListener("close", () => {
                desktop_notifications.notice_memory.delete(key);
            });
        }
    }
}

export function message_is_notifiable(message) {
    // Independent of the user's notification settings, are there
    // properties of the message that unconditionally mean we
    // shouldn't notify about it.

    if (message.sent_by_me) {
        return false;
    }

    // If a message is edited multiple times, we want to err on the side of
    // not spamming notifications.
    if (message.notification_sent) {
        return false;
    }

    // @-<username> mentions take precedence over muted-ness. Note
    // that @all mentions are still suppressed by muting.
    if (message.mentioned_me_directly) {
        return true;
    }

    // Messages to followed topics take precedence over muted-ness.
    if (
        message.type === "stream" &&
        user_topics.is_topic_followed(message.stream_id, message.topic)
    ) {
        return true;
    }

    // Messages to unmuted topics in muted streams may generate desktop notifications.
    if (
        message.type === "stream" &&
        stream_data.is_muted(message.stream_id) &&
        !user_topics.is_topic_unmuted(message.stream_id, message.topic)
    ) {
        return false;
    }

    if (message.type === "stream" && user_topics.is_topic_muted(message.stream_id, message.topic)) {
        return false;
    }

    // Everything else is on the table; next filter based on notification
    // settings.
    return true;
}

export function should_send_desktop_notification(message) {
    // Always notify for testing notifications.
    if (message.type === "test-notification") {
        return true;
    }

    // For streams, send if desktop notifications are enabled for all
    // message on this stream.
    if (
        message.type === "stream" &&
        stream_data.receives_notifications(message.stream_id, "desktop_notifications")
    ) {
        return true;
    }

    // enable_followed_topic_desktop_notifications determines whether we pop up
    // a notification for messages in followed topics.
    if (
        message.type === "stream" &&
        user_topics.is_topic_followed(message.stream_id, message.topic) &&
        user_settings.enable_followed_topic_desktop_notifications
    ) {
        return true;
    }

    // enable_desktop_notifications determines whether we pop up a
    // notification for direct messages, mentions, and/or alerts.
    if (!user_settings.enable_desktop_notifications) {
        return false;
    }

    // And then we need to check if the message is a direct message,
    // mention, wildcard mention with wildcard_mentions_notify, or alert.
    if (message.type === "private") {
        return true;
    }

    if (alert_words.notifies(message)) {
        return true;
    }

    if (message.mentioned_me_directly) {
        return true;
    }

    // The following blocks for 'wildcard mentions' and 'Followed topic wildcard mentions'
    // should be placed below (as they are right now) the 'user_settings.enable_desktop_notifications'
    // block because the global, stream-specific, and followed topic wildcard mention
    // settings are wrappers around the personal-mention setting.
    // wildcard mentions
    if (
        message.mentioned &&
        stream_data.receives_notifications(message.stream_id, "wildcard_mentions_notify")
    ) {
        return true;
    }

    // Followed topic wildcard mentions
    if (
        message.mentioned &&
        user_topics.is_topic_followed(message.stream_id, message.topic) &&
        user_settings.enable_followed_topic_wildcard_mentions_notify
    ) {
        return true;
    }

    return false;
}

export function should_send_audible_notification(message) {
    // If `None` is selected as the notification sound, never send
    // audible notifications regardless of other configuration.
    if (user_settings.notification_sound === "none") {
        return false;
    }

    // For streams, ding if sounds are enabled for all messages on
    // this stream.
    if (
        message.type === "stream" &&
        stream_data.receives_notifications(message.stream_id, "audible_notifications")
    ) {
        return true;
    }

    // enable_followed_topic_audible_notifications determines whether we ding
    // for messages in followed topics.
    if (
        message.type === "stream" &&
        user_topics.is_topic_followed(message.stream_id, message.topic) &&
        user_settings.enable_followed_topic_audible_notifications
    ) {
        return true;
    }

    // enable_sounds determines whether we ding for direct messages,
    // mentions, and/or alerts.
    if (!user_settings.enable_sounds) {
        return false;
    }

    // And then we need to check if the message is a direct message,
    // mention, wildcard mention with wildcard_mentions_notify, or alert.
    if (message.type === "private" || message.type === "test-notification") {
        return true;
    }

    if (alert_words.notifies(message)) {
        return true;
    }

    if (message.mentioned_me_directly) {
        return true;
    }

    // The following blocks for 'wildcard mentions' and 'Followed topic wildcard mentions'
    // should be placed below (as they are right now) the 'user_settings.enable_sounds'
    // block because the global, stream-specific, and followed topic wildcard mention
    // settings are wrappers around the personal-mention setting.
    // wildcard mentions
    if (
        message.mentioned &&
        stream_data.receives_notifications(message.stream_id, "wildcard_mentions_notify")
    ) {
        return true;
    }

    // Followed topic wildcard mentions
    if (
        message.mentioned &&
        user_topics.is_topic_followed(message.stream_id, message.topic) &&
        user_settings.enable_followed_topic_wildcard_mentions_notify
    ) {
        return true;
    }

    return false;
}

export function received_messages(messages) {
    for (const message of messages) {
        if (!message_is_notifiable(message)) {
            continue;
        }
        if (!unread.message_unread(message)) {
            // The message is already read; Zulip is currently in focus.
            continue;
        }

        message.notification_sent = true;

        if (should_send_desktop_notification(message)) {
            process_notification({
                message,
                desktop_notify: desktop_notifications.granted_desktop_notifications_permission(),
            });
        }
        if (should_send_audible_notification(message)) {
            ui_util.play_audio($("#user-notification-sound-audio")[0]);
        }
    }
}

export function send_test_notification(content) {
    received_messages([
        {
            id: Math.random(),
            type: "test-notification",
            sender_email: "notification-bot@zulip.com",
            sender_full_name: "Notification Bot",
            display_reply_to: "Notification Bot",
            content,
            unread: true,
        },
    ]);
}
