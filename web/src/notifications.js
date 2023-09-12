import $ from "jquery";

import render_message_sent_banner from "../templates/compose_banner/message_sent_banner.hbs";
import render_unmute_topic_banner from "../templates/compose_banner/unmute_topic_banner.hbs";

import * as alert_words from "./alert_words";
import * as blueslip from "./blueslip";
import * as compose_banner from "./compose_banner";
import * as favicon from "./favicon";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import * as message_parser from "./message_parser";
import * as narrow from "./narrow";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as people from "./people";
import * as spoilers from "./spoilers";
import * as stream_data from "./stream_data";
import * as ui_util from "./ui_util";
import * as unread from "./unread";
import {user_settings} from "./user_settings";
import * as user_topics from "./user_topics";

const notice_memory = new Map();

let NotificationAPI;

export function set_notification_api(n) {
    NotificationAPI = n;
}

if (window.electron_bridge && window.electron_bridge.new_notification) {
    class ElectronBridgeNotification extends EventTarget {
        constructor(title, options) {
            super();
            Object.assign(
                this,
                window.electron_bridge.new_notification(title, options, (type, eventInit) =>
                    this.dispatchEvent(new Event(type, eventInit)),
                ),
            );
        }

        static get permission() {
            return Notification.permission;
        }

        static async requestPermission(callback) {
            if (callback) {
                callback(await Promise.resolve(Notification.permission));
            }
            return Notification.permission;
        }
    }

    NotificationAPI = ElectronBridgeNotification;
} else if (window.Notification) {
    NotificationAPI = window.Notification;
}

export function get_notifications() {
    return notice_memory;
}

export function initialize({on_click_scroll_to_selected}) {
    $(window).on("focus", () => {
        for (const notice_mem_entry of notice_memory.values()) {
            notice_mem_entry.obj.close();
        }
        notice_memory.clear();
    });

    update_notification_sound_source($("#user-notification-sound-audio"), user_settings);

    register_click_handlers({on_click_scroll_to_selected});
}

export function update_notification_sound_source(container_elem, settings_object) {
    const notification_sound = settings_object.notification_sound;
    const audio_file_without_extension = "/static/audio/notification_sounds/" + notification_sound;
    container_elem
        .find(".notification-sound-source-ogg")
        .attr("src", `${audio_file_without_extension}.ogg`);
    container_elem
        .find(".notification-sound-source-mp3")
        .attr("src", `${audio_file_without_extension}.mp3`);

    if (notification_sound !== "none") {
        // Load it so that it is ready to be played; without this the old sound
        // is played.
        container_elem[0].load();
    }
}

export function permission_state() {
    if (NotificationAPI === undefined) {
        // act like notifications are blocked if they do not have access to
        // the notification API.
        return "denied";
    }
    return NotificationAPI.permission;
}

let unread_count = 0;
let pm_count = 0;

export function redraw_title() {
    // Update window title to reflect unread messages in current view
    const new_title =
        (unread_count ? "(" + unread_count + ") " : "") +
        narrow.narrow_title +
        " - " +
        page_params.realm_name +
        " - " +
        "Zulip";

    document.title = new_title;
}

export function update_unread_counts(counts) {
    const new_unread_count = unread.calculate_notifiable_count(counts);
    const new_pm_count = counts.direct_message_count;
    if (new_unread_count === unread_count && new_pm_count === pm_count) {
        return;
    }

    unread_count = new_unread_count;
    pm_count = new_pm_count;

    // Indicate the message count in the favicon
    favicon.update_favicon(unread_count, pm_count);

    // Notify the current desktop app's UI about the new unread count.
    if (window.electron_bridge !== undefined) {
        window.electron_bridge.send_event("total_unread_count", unread_count);
    }

    // TODO: Add a `window.electron_bridge.updateDirectMessageCount(new_pm_count);` call?

    redraw_title();
}

function notify_unmute(muted_narrow, stream_id, topic_name) {
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
    banner_text,
    classname,
    above_composebox_narrow_url,
    link_msg_id,
    link_text,
) {
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

function get_notification_content(message) {
    let content;
    // Convert the content to plain text, replacing emoji with their alt text
    const $content = $("<div>").html(message.content);
    ui_util.replace_emoji_with_text($content);
    spoilers.hide_spoilers_in_notification($content);

    if (
        $content.text().trim() === "" &&
        (message_parser.message_has_image(message) ||
            message_parser.message_has_attachment(message))
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
        content = "New direct message from " + message.sender_full_name;
    }

    if (content.length > 150) {
        let i;
        // Truncate content at a word boundary
        for (i = 150; i > 0; i -= 1) {
            if (content[i] === " ") {
                break;
            }
        }
        content = content.slice(0, i);
        content += " [...]";
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

function get_notification_title(message, content, msg_count) {
    let title = message.sender_full_name;
    let other_recipients;

    if (msg_count > 1) {
        title = msg_count + " messages from " + title;
    }

    switch (message.type) {
        case "test-notification":
            other_recipients = remove_sender_from_list_of_recipients(message);
            break;
        case "private":
            other_recipients = remove_sender_from_list_of_recipients(message);
            if (message.display_recipient.length > 2) {
                // If the message has too many recipients to list them all...
                if (content.length + title.length + other_recipients.length > 230) {
                    // Then count how many people are in the conversation and summarize
                    // by saying the conversation is with "you and [number] other people"
                    other_recipients =
                        other_recipients.replaceAll(/[^,]/g, "").length + " other people";
                }

                title += " (to you and " + other_recipients + ")";
            } else {
                title += " (to you)";
            }
            break;
        case "stream": {
            const stream_name = stream_data.get_stream_name_from_id(message.stream_id);
            title += " (to " + stream_name + " > " + message.topic + ")";
            break;
        }
    }

    return title;
}

export function process_notification(notification) {
    const message = notification.message;
    const content = get_notification_content(message);
    const key = get_notification_key(message);
    let notification_object;
    let msg_count = 1;

    debug_notification_source_value(message);

    if (notice_memory.has(key)) {
        msg_count = notice_memory.get(key).msg_count + 1;
        notification_object = notice_memory.get(key).obj;
        notification_object.close();
    }

    const title = get_notification_title(message, content, msg_count);

    if (notification.desktop_notify) {
        const icon_url = people.small_avatar_url(message);
        notification_object = new NotificationAPI(title, {
            icon: icon_url,
            body: content,
            tag: message.id,
        });
        notice_memory.set(key, {
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
                    narrow.by_topic(message.id, {trigger: "notification"});
                }
                window.focus();
            });
            notification_object.addEventListener("close", () => {
                notice_memory.delete(key);
            });
        }
    }
}

export function close_notification(message) {
    for (const [key, notice_mem_entry] of notice_memory) {
        if (notice_mem_entry.message_id === message.id) {
            notice_mem_entry.obj.close();
            notice_memory.delete(key);
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

export function granted_desktop_notifications_permission() {
    return NotificationAPI && NotificationAPI.permission === "granted";
}

export function request_desktop_notifications_permission() {
    if (NotificationAPI) {
        NotificationAPI.requestPermission();
    }
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
                desktop_notify: granted_desktop_notifications_permission(),
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

// Note that this returns values that are not HTML-escaped, for use in
// Handlebars templates that will do further escaping.
function get_message_header(message) {
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

export function get_muted_narrow(message) {
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

export function get_local_notify_mix_reason(message) {
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
        return $t({defaultMessage: "Sent! Your message is outside your current narrow."});
    }

    return undefined;
}

export function notify_local_mixes(messages, need_user_to_scroll) {
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

        const muted_narrow = get_muted_narrow(message);
        if (muted_narrow) {
            notify_unmute(muted_narrow, message.stream_id, message.topic);
            // We don't `continue` after showing the unmute banner, allowing multiple
            // banners (at max 2 including the unmute banner) to be shown at once,
            // as it's common for the unmute case to occur simultaneously with
            // another banner's case, like sending a message to another narrow.
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
            {defaultMessage: "Narrow to {message_recipient}"},
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

function get_above_composebox_narrow_url(message) {
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
export function notify_messages_outside_current_search(messages) {
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

export function reify_message_id(opts) {
    const old_id = opts.old_id;
    const new_id = opts.new_id;

    // If a message ID that we're currently storing (as a link) has changed,
    // update that link as well
    for (const e of $("#compose_banners a")) {
        const $elem = $(e);
        const message_id = $elem.data("message-id");

        if (message_id === old_id) {
            $elem.data("message-id", new_id);
            compose_banner.set_scroll_to_message_banner_message_id(new_id);
        }
    }
}

function register_click_handlers({on_click_scroll_to_selected}) {
    $("#compose_banners").on(
        "click",
        ".narrow_to_recipient .above_compose_banner_action_link",
        (e) => {
            const message_id = $(e.currentTarget).data("message-id");
            narrow.by_topic(message_id, {trigger: "compose_notification"});
            e.stopPropagation();
            e.preventDefault();
        },
    );
    $("#compose_banners").on(
        "click",
        ".sent_scroll_to_view .above_compose_banner_action_link",
        (e) => {
            const message_id = $(e.currentTarget).data("message-id");
            message_lists.current.select_id(message_id);
            on_click_scroll_to_selected();
            compose_banner.clear_message_sent_banners(false);
            e.stopPropagation();
            e.preventDefault();
        },
    );
}
