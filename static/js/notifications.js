"use strict";

const _ = require("lodash");

const render_compose_notification = require("../templates/compose_notification.hbs");
const render_notification = require("../templates/notification.hbs");

const people = require("./people");
const settings_config = require("./settings_config");

const notice_memory = new Map();

// When you start Zulip, window_has_focus should be true, but it might not be the
// case after a server-initiated reload.
let window_has_focus = document.hasFocus && document.hasFocus();

let supports_sound;

const unread_pms_favicon = "/static/images/favicon/favicon-pms.png?v=4";
let current_favicon;
let previous_favicon;
let flashing = false;

let NotificationAPI;

exports.set_notification_api = function (n) {
    NotificationAPI = n;
};

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

exports.get_notifications = function () {
    return notice_memory;
};

function get_audio_file_path(audio_element, audio_file_without_extension) {
    if (audio_element.canPlayType('audio/ogg; codecs="vorbis"')) {
        return audio_file_without_extension + ".ogg";
    }

    return audio_file_without_extension + ".mp3";
}

exports.initialize = function () {
    $(window)
        .on("focus", () => {
            window_has_focus = true;

            for (const notice_mem_entry of notice_memory.values()) {
                notice_mem_entry.obj.close();
            }
            notice_memory.clear();

            // Update many places on the DOM to reflect unread
            // counts.
            unread_ops.process_visible();
        })
        .on("blur", () => {
            window_has_focus = false;
        });

    const audio = $("<audio>");
    if (audio[0].canPlayType === undefined) {
        supports_sound = false;
    } else {
        supports_sound = true;

        $("#notifications-area").append(audio);
        audio.append($("<source>").attr("loop", "yes"));
        const source = $("#notifications-area audio source");

        if (audio[0].canPlayType('audio/ogg; codecs="vorbis"')) {
            source.attr("type", "audio/ogg");
        } else {
            source.attr("type", "audio/mpeg");
        }

        const audio_file_without_extension =
            "/static/audio/notification_sounds/" + page_params.notification_sound;
        source.attr("src", get_audio_file_path(audio[0], audio_file_without_extension));
    }
};

function update_notification_sound_source() {
    // Simplified version of the source creation in `exports.initialize`, for
    // updating the source instead of creating it for the first time.
    const audio = $("#notifications-area audio");
    const source = $("#notifications-area audio source");
    const audio_file_without_extension =
        "/static/audio/notification_sounds/" + page_params.notification_sound;
    source.attr("src", get_audio_file_path(audio[0], audio_file_without_extension));

    // Load it so that it is ready to be played; without this the old sound
    // is played.
    $("#notifications-area").find("audio")[0].load();
}

exports.permission_state = function () {
    if (NotificationAPI === undefined) {
        // act like notifications are blocked if they do not have access to
        // the notification API.
        return "denied";
    }
    return NotificationAPI.permission;
};

let new_message_count = 0;

exports.update_title_count = function (count) {
    new_message_count = count;
    exports.redraw_title();
};

exports.redraw_title = function () {
    // Update window title and favicon to reflect unread messages in current view
    let n;

    const new_title =
        (new_message_count ? "(" + new_message_count + ") " : "") +
        narrow.narrow_title +
        " - " +
        page_params.realm_name +
        " - " +
        "Zulip";

    if (document.title === new_title) {
        return;
    }

    document.title = new_title;

    // IE doesn't support PNG favicons, *shrug*
    if (!/msie/i.test(navigator.userAgent)) {
        // Indicate the message count in the favicon
        if (new_message_count) {
            // Make sure we're working with a number, as a defensive programming
            // measure.  And we don't have images above 99, so display those as
            // 'infinite'.
            n = +new_message_count;
            if (n > 99) {
                n = "infinite";
            }

            current_favicon = previous_favicon = "/static/images/favicon/favicon-" + n + ".png?v=4";
        } else {
            current_favicon = previous_favicon = "/static/images/favicon.svg?v=4";
        }
        favicon.set(current_favicon);
    }

    // Notify the current desktop app's UI about the new unread count.
    if (window.electron_bridge !== undefined) {
        window.electron_bridge.send_event("total_unread_count", new_message_count);
    }
};

function flash_pms() {
    // When you have unread PMs, toggle the favicon between the unread count and
    // a special icon indicating that you have unread PMs.
    if (unread.get_counts().private_message_count > 0) {
        if (current_favicon === unread_pms_favicon) {
            favicon.set(previous_favicon);
            current_favicon = previous_favicon;
            previous_favicon = unread_pms_favicon;
        } else {
            favicon.set(unread_pms_favicon);
            previous_favicon = current_favicon;
            current_favicon = unread_pms_favicon;
        }
        // Toggle every 2 seconds.
        setTimeout(flash_pms, 2000);
    } else {
        flashing = false;
        // You have no more unread PMs, so back to only showing the unread
        // count.
        favicon.set(current_favicon);
    }
}

exports.update_pm_count = function () {
    // TODO: Add a `window.electron_bridge.updatePMCount(new_pm_count);` call?
    if (!flashing) {
        flashing = true;
        flash_pms();
    }
};

exports.window_has_focus = function () {
    return window_has_focus;
};

function in_browser_notify(message, title, content, raw_operators, opts) {
    const notification_html = $(
        render_notification({
            gravatar_url: people.small_avatar_url(message),
            title,
            content,
            message_id: message.id,
        }),
    );

    $(".top-right")
        .notify({
            message: {
                html: notification_html,
            },
            fadeOut: {
                enabled: true,
                delay: 4000,
            },
        })
        .show();

    $(".notification[data-message-id='" + message.id + "']")
        .expectOne()
        .data("narrow", {
            raw_operators,
            opts_notif: opts,
        });
}

exports.notify_above_composebox = function (note, link_class, link_msg_id, link_text) {
    const notification_html = $(
        render_compose_notification({
            note,
            link_class,
            link_msg_id,
            link_text,
        }),
    );
    exports.clear_compose_notifications();
    $("#out-of-view-notification").append(notification_html);
    $("#out-of-view-notification").show();
};

if (window.electron_bridge !== undefined) {
    // The code below is for sending a message received from notification reply which
    // is often referred to as inline reply feature. This is done so desktop app doesn't
    // have to depend on channel.post for setting crsf_token and narrow.by_topic
    // to narrow to the message being sent.
    if (window.electron_bridge.set_send_notification_reply_message_supported !== undefined) {
        window.electron_bridge.set_send_notification_reply_message_supported(true);
    }
    window.electron_bridge.on_event("send_notification_reply_message", (message_id, reply) => {
        const message = message_store.get(message_id);
        const data = {
            type: message.type,
            content: reply,
            to: message.type === "private" ? message.reply_to : message.stream,
            topic: message.topic,
        };

        function success() {
            if (message.type === "stream") {
                narrow.by_topic(message_id, {trigger: "desktop_notification_reply"});
            } else {
                narrow.by_recipient(message_id, {trigger: "desktop_notification_reply"});
            }
        }

        function error(error) {
            window.electron_bridge.send_event("send_notification_reply_message_failed", {
                data,
                message_id,
                error,
            });
        }

        channel.post({
            url: "/json/messages",
            data,
            success,
            error,
        });
    });
}

function process_notification(notification) {
    let i;
    let notification_object;
    let key;
    let content;
    let other_recipients;
    const message = notification.message;
    let title = message.sender_full_name;
    let msg_count = 1;
    let notification_source;
    let raw_operators = [];
    const opts = {trigger: "notification click"};
    // Convert the content to plain text, replacing emoji with their alt text
    content = $("<div/>").html(message.content);
    ui.replace_emoji_with_text(content);
    spoilers.hide_spoilers_in_notification(content);
    content = content.text();

    const topic = message.topic;

    if (message.is_me_message) {
        content = message.sender_full_name + content.slice(3);
    }

    if (message.type === "private" || message.type === "test-notification") {
        if (
            page_params.pm_content_in_desktop_notifications !== undefined &&
            !page_params.pm_content_in_desktop_notifications
        ) {
            content = "New private message from " + message.sender_full_name;
        }
        key = message.display_reply_to;
        other_recipients = message.display_reply_to;
        // Remove the sender from the list of other recipients
        other_recipients = other_recipients.replace(", " + message.sender_full_name, "");
        other_recipients = other_recipients.replace(message.sender_full_name + ", ", "");
        notification_source = "pm";
    } else {
        key = message.sender_full_name + " to " + message.stream + " > " + topic;
        if (message.mentioned) {
            notification_source = "mention";
        } else if (message.alerted) {
            notification_source = "alert";
        } else {
            notification_source = "stream";
        }
    }
    blueslip.debug("Desktop notification from source " + notification_source);

    if (content.length > 150) {
        // Truncate content at a word boundary
        for (i = 150; i > 0; i -= 1) {
            if (content[i] === " ") {
                break;
            }
        }
        content = content.substring(0, i);
        content += " [...]";
    }

    if (notice_memory.has(key)) {
        msg_count = notice_memory.get(key).msg_count + 1;
        title = msg_count + " messages from " + title;
        notification_object = notice_memory.get(key).obj;
        notification_object.close();
    }

    if (message.type === "private") {
        if (message.display_recipient.length > 2) {
            // If the message has too many recipients to list them all...
            if (content.length + title.length + other_recipients.length > 230) {
                // Then count how many people are in the conversation and summarize
                // by saying the conversation is with "you and [number] other people"
                other_recipients = other_recipients.replace(/[^,]/g, "").length + " other people";
            }

            title += " (to you and " + other_recipients + ")";
        } else {
            title += " (to you)";
        }

        raw_operators = [{operand: message.reply_to, operator: "pm-with"}];
    }

    if (message.type === "stream") {
        title += " (to " + message.stream + " > " + topic + ")";
        raw_operators = [
            {operator: "stream", operand: message.stream},
            {operator: "topic", operand: topic},
        ];
    }

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

        if (_.isFunction(notification_object.addEventListener)) {
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
    } else {
        in_browser_notify(message, title, content, raw_operators, opts);
    }
}

exports.process_notification = process_notification;

exports.close_notification = function (message) {
    for (const [key, notice_mem_entry] of notice_memory) {
        if (notice_mem_entry.message_id === message.id) {
            notice_mem_entry.obj.close();
            notice_memory.delete(key);
        }
    }
};

exports.message_is_notifiable = function (message) {
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

    // Messages to muted streams that don't mention us specifically
    // are not notifiable.
    if (message.type === "stream" && stream_data.is_muted(message.stream_id)) {
        return false;
    }

    if (message.type === "stream" && muting.is_topic_muted(message.stream_id, message.topic)) {
        return false;
    }

    // Everything else is on the table; next filter based on notification
    // settings.
    return true;
};

exports.should_send_desktop_notification = function (message) {
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

    // enable_desktop_notifications determines whether we pop up a
    // notification for PMs/mentions/alerts
    if (!page_params.enable_desktop_notifications) {
        return false;
    }

    // And then we need to check if the message is a PM, mention,
    // wildcard mention with wildcard_mentions_notify, or alert.
    if (message.type === "private") {
        return true;
    }

    if (alert_words.notifies(message)) {
        return true;
    }

    if (message.mentioned_me_directly) {
        return true;
    }

    // wildcard mentions
    if (
        message.mentioned &&
        stream_data.receives_notifications(message.stream_id, "wildcard_mentions_notify")
    ) {
        return true;
    }

    return false;
};

exports.should_send_audible_notification = function (message) {
    // For streams, ding if sounds are enabled for all messages on
    // this stream.
    if (
        message.type === "stream" &&
        stream_data.receives_notifications(message.stream_id, "audible_notifications")
    ) {
        return true;
    }

    // enable_sounds determines whether we ding for PMs/mentions/alerts
    if (!page_params.enable_sounds) {
        return false;
    }

    // And then we need to check if the message is a PM, mention,
    // wildcard mention with wildcard_mentions_notify, or alert.
    if (message.type === "private" || message.type === "test-notification") {
        return true;
    }

    if (alert_words.notifies(message)) {
        return true;
    }

    if (message.mentioned_me_directly) {
        return true;
    }

    // wildcard mentions
    if (
        message.mentioned &&
        stream_data.receives_notifications(message.stream_id, "wildcard_mentions_notify")
    ) {
        return true;
    }

    return false;
};

exports.granted_desktop_notifications_permission = function () {
    return NotificationAPI && NotificationAPI.permission === "granted";
};

exports.request_desktop_notifications_permission = function () {
    if (NotificationAPI) {
        return NotificationAPI.requestPermission();
    }
};

exports.received_messages = function (messages) {
    for (const message of messages) {
        if (!exports.message_is_notifiable(message)) {
            continue;
        }
        if (!unread.message_unread(message)) {
            // The message is already read; Zulip is currently in focus.
            continue;
        }

        message.notification_sent = true;

        if (exports.should_send_desktop_notification(message)) {
            process_notification({
                message,
                desktop_notify: exports.granted_desktop_notifications_permission(),
            });
        }
        if (exports.should_send_audible_notification(message) && supports_sound) {
            $("#notifications-area").find("audio")[0].play();
        }
    }
};

exports.send_test_notification = function (content) {
    exports.received_messages([
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
};

function get_message_header(message) {
    if (message.type === "stream") {
        return message.stream + " > " + message.topic;
    }
    if (message.display_recipient.length > 2) {
        return i18n.t("group private messages with __recipient__", {
            recipient: message.display_reply_to,
        });
    }
    if (people.is_current_user(message.reply_to)) {
        return i18n.t("private messages with yourself");
    }
    return i18n.t("private messages with __recipient__", {recipient: message.display_reply_to});
}

exports.get_local_notify_mix_reason = function (message) {
    const row = current_msg_list.get_row(message.id);
    if (row.length > 0) {
        // If our message is in the current message list, we do
        // not have a mix, so we are happy.
        return;
    }

    if (message.type === "stream" && muting.is_topic_muted(message.stream_id, message.topic)) {
        return i18n.t("Sent! Your message was sent to a topic you have muted.");
    }

    if (message.type === "stream" && stream_data.is_muted(message.stream_id)) {
        return i18n.t("Sent! Your message was sent to a stream you have muted.");
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
        return i18n.t("Sent! Your message is outside your current narrow.");
    }
};

exports.notify_local_mixes = function (messages, need_user_to_scroll) {
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

        let reason = exports.get_local_notify_mix_reason(message);

        if (!reason) {
            if (need_user_to_scroll) {
                reason = i18n.t("Sent! Scroll down to view your message.");
                exports.notify_above_composebox(reason, "", null, "");
                setTimeout(() => {
                    $("#out-of-view-notification").hide();
                }, 3000);
            }

            // This is the HAPPY PATH--for most messages we do nothing
            // other than maybe sending the above message.
            continue;
        }

        const link_msg_id = message.id;
        const link_class = "compose_notification_narrow_by_topic";
        const link_text = i18n.t("Narrow to __- message_recipient__", {
            message_recipient: get_message_header(message),
        });

        exports.notify_above_composebox(reason, link_class, link_msg_id, link_text);
    }
};

// for callback when we have to check with the server if a message should be in
// the current_msg_list (!can_apply_locally; a.k.a. "a search").
exports.notify_messages_outside_current_search = function (messages) {
    for (const message of messages) {
        if (!people.is_current_user(message.sender_email)) {
            continue;
        }
        const link_text = i18n.t("Narrow to __- message_recipient__", {
            message_recipient: get_message_header(message),
        });
        exports.notify_above_composebox(
            i18n.t("Sent! Your recent message is outside the current search."),
            "compose_notification_narrow_by_topic",
            message.id,
            link_text,
        );
    }
};

exports.clear_compose_notifications = function () {
    $("#out-of-view-notification").empty();
    $("#out-of-view-notification").stop(true, true);
    $("#out-of-view-notification").hide();
};

exports.reify_message_id = function (opts) {
    const old_id = opts.old_id;
    const new_id = opts.new_id;

    // If a message ID that we're currently storing (as a link) has changed,
    // update that link as well
    for (const e of $("#out-of-view-notification a")) {
        const elem = $(e);
        const message_id = elem.data("message-id");

        if (message_id === old_id) {
            elem.data("message-id", new_id);
        }
    }
};

exports.register_click_handlers = function () {
    $("#out-of-view-notification").on("click", ".compose_notification_narrow_by_topic", (e) => {
        const message_id = $(e.currentTarget).data("message-id");
        narrow.by_topic(message_id, {trigger: "compose_notification"});
        e.stopPropagation();
        e.preventDefault();
    });
    $("#out-of-view-notification").on("click", ".compose_notification_scroll_to_message", (e) => {
        const message_id = $(e.currentTarget).data("message-id");
        current_msg_list.select_id(message_id);
        navigate.scroll_to_selected();
        e.stopPropagation();
        e.preventDefault();
    });
    $("#out-of-view-notification").on("click", ".out-of-view-notification-close", (e) => {
        exports.clear_compose_notifications();
        e.stopPropagation();
        e.preventDefault();
    });
};

exports.handle_global_notification_updates = function (notification_name, setting) {
    // Update the global settings checked when determining if we should notify
    // for a given message. These settings do not affect whether or not a
    // particular stream should receive notifications.
    if (settings_config.all_notification_settings.includes(notification_name)) {
        page_params[notification_name] = setting;
    }

    if (settings_config.stream_notification_settings.includes(notification_name)) {
        notification_name = notification_name.replace("enable_stream_", "");
        stream_ui_updates.update_notification_setting_checkbox(notification_name);
    }

    if (notification_name === "notification_sound") {
        // Change the sound source with the new page `notification_sound`.
        update_notification_sound_source();
    }
};

window.notifications = exports;
