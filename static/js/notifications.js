var notifications = (function () {

var exports = {};

var notice_memory = {};

// When you start Zulip, window_has_focus should be true, but it might not be the
// case after a server-initiated reload.
var window_has_focus = document.hasFocus && document.hasFocus();

var supports_sound;

var unread_pms_favicon = '/static/images/favicon/favicon-pms.png';
var current_favicon;
var previous_favicon;
var flashing = false;

var notifications_api;

exports.set_notification_api = function (n) {
    notifications_api = n;
};

if (window.webkitNotifications) {
    notifications_api = window.webkitNotifications;
} else if (window.Notification) {
    // Build a shim to the new notification API
    notifications_api = {
        checkPermission: function checkPermission() {
            if (window.Notification.permission === 'granted') {
                return 0;
            }
            return 2;
        },
        requestPermission: window.Notification.requestPermission,
        createNotification: function createNotification(icon, title, content, tag) {
            var notification_object = new window.Notification(title, {icon: icon,
                                                                      body: content,
                                                                      tag: tag});
            notification_object.show = function () {};
            notification_object.cancel = function () { notification_object.close(); };
            return notification_object;
        },
    };
}


function browser_desktop_notifications_on() {
    return notifications_api &&
            // Firefox on Ubuntu claims to do webkitNotifications but its notifications are terrible
            /webkit/i.test(navigator.userAgent) &&
            // 0 is PERMISSION_ALLOWED
            notifications_api.checkPermission() === 0;
}

function cancel_notification_object(notification_object) {
    // We must remove the .onclose so that it does not trigger on .cancel
    notification_object.onclose = function () {};
    notification_object.onclick = function () {};
    notification_object.cancel();
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
    $(window).focus(function () {
        window_has_focus = true;

        _.each(notice_memory, function (notice_mem_entry) {
            cancel_notification_object(notice_mem_entry.obj);
        });
        notice_memory = {};

        // Update many places on the DOM to reflect unread
        // counts.
        unread_ops.process_visible();

    }).blur(function () {
        window_has_focus = false;
    });

    var audio = $("<audio>");
    if (audio[0].canPlayType === undefined) {
        supports_sound = false;
    } else {
        supports_sound = true;

        $("#notifications-area").append(audio);
        audio.append($("<source>").attr("loop", "yes"));
        var source = $("#notifications-area audio source");

        if (audio[0].canPlayType('audio/ogg; codecs="vorbis"')) {
            source.attr("type", "audio/ogg");
        } else {
            source.attr("type", "audio/mpeg");
        }

        var audio_file_without_extension
            = "/static/audio/notification_sounds/" + page_params.notification_sound;
        source.attr("src", get_audio_file_path(audio[0], audio_file_without_extension));
    }
};

function update_notification_sound_source() {
    // Simplified version of the source creation in `exports.initialize`, for
    // updating the source instead of creating it for the first time.
    var audio = $("#notifications-area audio");
    var source = $("#notifications-area audio source");
    var audio_file_without_extension
        = "/static/audio/notification_sounds/" + page_params.notification_sound;
    source.attr("src", get_audio_file_path(audio[0], audio_file_without_extension));

    // Load it so that it is ready to be played; without this the old sound
    // is played.
    $("#notifications-area").find("audio")[0].load();
}

exports.permission_state = function () {
    if (window.Notification === undefined) {
        // act like notifications are blocked if they do not have access to
        // the notification API.
        return "denied";
    }
    return window.Notification.permission;
};

var new_message_count = 0;

exports.update_title_count = function (count) {
    new_message_count = count;
    exports.redraw_title();
};

exports.redraw_title = function () {
    // Update window title and favicon to reflect unread messages in current view
    var n;

    var new_title = (new_message_count ? "(" + new_message_count + ") " : "")
        + narrow.narrow_title + " - "
        + page_params.realm_name + " - "
        + "Zulip";

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
                n = 'infinite';
            }

            current_favicon = previous_favicon = '/static/images/favicon/favicon-' + n + '.png';
        } else {
            current_favicon = previous_favicon = '/static/favicon.ico?v=2';
        }
        favicon.set(current_favicon);
    }

    // Notify the current desktop app's UI about the new unread count.
    if (window.electron_bridge !== undefined) {
        window.electron_bridge.send_event('total_unread_count', new_message_count);
    }
};

exports.show_history_limit_message = function () {
    $(".top-messages-logo").hide();
    $(".history-limited-box").show();
    narrow.hide_empty_narrow_message();
};

exports.hide_history_limit_message = function () {
    $(".top-messages-logo").show();
    $(".history-limited-box").hide();
};

exports.hide_or_show_history_limit_message = function (msg_list) {
    if (msg_list !== current_msg_list) {
        return;
    }

    if (msg_list.fetch_status.history_limited()) {
        notifications.show_history_limit_message();
    } else {
        notifications.hide_history_limit_message();
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
    var notification_html = $(templates.render('notification', {
        gravatar_url: people.small_avatar_url(message),
        title: title,
        content: content,
        message_id: message.id,
    }));

    $(".top-right").notify({
        message: {
            html: notification_html,
        },
        fadeOut: {
            enabled: true,
            delay: 4000,
        },
    }).show();

    $(".notification[data-message-id='" + message.id + "']").expectOne().data("narrow", {
        raw_operators: raw_operators,
        opts_notif: opts,
    });
}

exports.notify_above_composebox = function (note, link_class, link_msg_id, link_text) {
    var notification_html = $(templates.render('compose_notification', {note: note,
                                                                        link_class: link_class,
                                                                        link_msg_id: link_msg_id,
                                                                        link_text: link_text}));
    exports.clear_compose_notifications();
    $('#out-of-view-notification').append(notification_html);
    $('#out-of-view-notification').show();
};

function process_notification(notification) {
    var i;
    var notification_object;
    var key;
    var content;
    var other_recipients;
    var message = notification.message;
    var title = message.sender_full_name;
    var msg_count = 1;
    var notification_source;
    var raw_operators = [];
    var opts = {trigger: "notification click"};
    // Convert the content to plain text, replacing emoji with their alt text
    content = $('<div/>').html(message.content);
    ui.replace_emoji_with_text(content);
    content = content.text();

    var topic = util.get_message_topic(message);

    if (message.is_me_message) {
        content = message.sender_full_name + content.slice(3);
    }

    if (message.type === "private") {
        if (page_params.pm_content_in_desktop_notifications !== undefined
            && !page_params.pm_content_in_desktop_notifications) {
            content = "New private message from " + message.sender_full_name;
        }
        key = message.display_reply_to;
        other_recipients = message.display_reply_to;
        // Remove the sender from the list of other recipients
        other_recipients = other_recipients.replace(", " + message.sender_full_name, "");
        other_recipients = other_recipients.replace(message.sender_full_name + ", ", "");
        notification_source = 'pm';
    } else {
        key = message.sender_full_name + " to " +
              message.stream + " > " + topic;
        if (message.mentioned) {
            notification_source = 'mention';
        } else if (message.alerted) {
            notification_source = 'alert';
        } else {
            notification_source = 'stream';
        }
    }
    blueslip.debug("Desktop notification from source " + notification_source);

    if (content.length > 150) {
        // Truncate content at a word boundary
        for (i = 150; i > 0; i -= 1) {
            if (content[i] === ' ') {
                break;
            }
        }
        content = content.substring(0, i);
        content += " [...]";
    }

    if (notice_memory[key] !== undefined) {
        msg_count = notice_memory[key].msg_count + 1;
        title = msg_count + " messages from " + title;
        notification_object = notice_memory[key].obj;
        cancel_notification_object(notification_object);
    }

    if (message.type === "private") {
        if (message.display_recipient.length > 2) {
            // If the message has too many recipients to list them all...
            if (content.length + title.length + other_recipients.length > 230) {
                // Then count how many people are in the conversation and summarize
                // by saying the conversation is with "you and [number] other people"
                other_recipients = other_recipients.replace(/[^,]/g, "").length +
                                   " other people";
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

    if (notification.webkit_notify === true) {
        var icon_url = people.small_avatar_url(message);
        notice_memory[key] = {
            obj: notifications_api.createNotification(icon_url, title, content, message.id),
            msg_count: msg_count,
            message_id: message.id,
        };
        notification_object = notice_memory[key].obj;
        notification_object.onclick = function () {
            notification_object.cancel();
            if (feature_flags.clicking_notification_causes_narrow) {
                narrow.by_topic(message.id, {trigger: 'notification'});
            }
            window.focus();
        };
        notification_object.onclose = function () {
            delete notice_memory[key];
        };
        notification_object.show();
    } else if (notification.webkit_notify === false && typeof Notification !== "undefined" && /mozilla/i.test(navigator.userAgent) === true) {
        Notification.requestPermission(function (perm) {
            if (perm === 'granted') {
                notification_object = new Notification(title, {
                    body: content,
                    iconUrl: people.small_avatar_url(message),
                    tag: message.id,
                });
                notification_object.onclick = function () {
                    // We don't need to bring the browser window into focus explicitly
                    // by calling `window.focus()` as well as don't need to clear the
                    // notification since it is the default behavior in Firefox.
                    if (feature_flags.clicking_notification_causes_narrow) {
                        narrow.by_topic(message.id, {trigger: 'notification'});
                    }
                };
            } else {
                in_browser_notify(message, title, content, raw_operators, opts);
            }
        });
    } else if (notification.webkit_notify === false) {
        in_browser_notify(message, title, content, raw_operators, opts);
    }
}

exports.process_notification = process_notification;

exports.close_notification = function (message) {
    _.each(Object.keys(notice_memory), function (key) {
        if (notice_memory[key].message_id === message.id) {
            cancel_notification_object(notice_memory[key].obj);
            delete notice_memory[key];
        }
    });
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
    if (message.type === "stream" &&
        !stream_data.in_home_view(message.stream_id)) {
        return false;
    }

    if (message.type === "stream" &&
        muting.is_topic_muted(message.stream_id, util.get_message_topic(message))) {
        return false;
    }

    // Everything else is on the table; next filter based on notification
    // settings.
    return true;
};

function should_send_desktop_notification(message) {
    // For streams, send if desktop notifications are enabled for this
    // stream.
    if (message.type === "stream" &&
        stream_data.receives_desktop_notifications(message.stream)) {
        return true;
    }

    // For PMs and @-mentions, send if desktop notifications are
    // enabled.
    if (message.type === "private" &&
        page_params.enable_desktop_notifications) {
        return true;
    }

    // For alert words and @-mentions, send if desktop notifications
    // are enabled.
    if (alert_words.notifies(message) &&
        page_params.enable_desktop_notifications) {
        return true;
    }

    if (message.mentioned &&
        page_params.enable_desktop_notifications) {
        return true;
    }

    return false;
}

function should_send_audible_notification(message) {
    // For streams, ding if sounds are enabled for this stream.
    if (message.type === "stream" &&
        stream_data.receives_audible_notifications(message.stream)) {
        return true;
    }

    // For PMs and @-mentions, ding if sounds are enabled.
    if (message.type === "private" && page_params.enable_sounds) {
        return true;
    }

    // For alert words and @-mentions, ding if sounds are enabled.
    if (alert_words.notifies(message) && page_params.enable_sounds) {
        return true;
    }

    if (message.mentioned && page_params.enable_sounds) {
        return true;
    }

    return false;
}

exports.granted_desktop_notifications_permission = function () {
    return notifications_api &&
            // 0 is PERMISSION_ALLOWED
            notifications_api.checkPermission() === 0;
};


exports.request_desktop_notifications_permission = function () {
    if (notifications_api) {
        return notifications_api.requestPermission();
    }
};

exports.received_messages = function (messages) {
    _.each(messages, function (message) {
        if (!exports.message_is_notifiable(message)) {
            return;
        }
        if (!unread.message_unread(message)) {
            // The message is already read; Zulip is currently in focus.
            return;
        }

        message.notification_sent = true;

        if (should_send_desktop_notification(message)) {
            if (browser_desktop_notifications_on()) {
                process_notification({message: message, webkit_notify: true});
            } else {
                process_notification({message: message, webkit_notify: false});
            }
        }
        if (should_send_audible_notification(message) && supports_sound) {
            $("#notifications-area").find("audio")[0].play();
        }
    });
};

function get_message_header(message) {
    if (message.type === "stream") {
        return message.stream + " > " + util.get_message_topic(message);
    }
    if (message.display_recipient.length > 2) {
        return i18n.t("group private messages with __recipient__",
                      {recipient: message.display_reply_to});
    }
    if (people.is_current_user(message.reply_to)) {
        return i18n.t("private messages with yourself");
    }
    return i18n.t("private messages with __recipient__",
                  {recipient: message.display_reply_to});
}

exports.get_local_notify_mix_reason = function (message) {
    var row = current_msg_list.get_row(message.id);
    if (row.length > 0) {
        // If our message is in the current message list, we do
        // not have a mix, so we are happy.
        return;
    }

    if (message.type === "stream" && muting.is_topic_muted(message.stream_id, util.get_message_topic(message))) {
        return i18n.t("Sent! Your message was sent to a topic you have muted.");
    }

    if (message.type === "stream" && !stream_data.in_home_view(message.stream_id)) {
        return i18n.t("Sent! Your message was sent to a stream you have muted.");
    }

    // offscreen because it is outside narrow
    // we can only look for these on non-search (can_apply_locally) messages
    // see also: exports.notify_messages_outside_current_search
    return i18n.t("Sent! Your message is outside your current narrow.");
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

    _.each(messages, function (message) {
        if (!people.is_my_user_id(message.sender_id)) {
            // This can happen if the client is offline for a while
            // around the time this client sends a message; see the
            // caller of message_events.insert_new_messages.
            blueslip.info('Slightly unexpected: A message not sent by us batches with those that were.');
            return;
        }

        var reason = exports.get_local_notify_mix_reason(message);

        if (!reason) {
            if (need_user_to_scroll) {
                reason = i18n.t("Sent! Scroll down to view your message.");
                exports.notify_above_composebox(reason, "", null, "");
                setTimeout(function () {
                    $('#out-of-view-notification').hide();
                }, 3000);
            }

            // This is the HAPPY PATH--for most messages we do nothing
            // other than maybe sending the above message.
            return;
        }

        var link_msg_id = message.id;
        var link_class = "compose_notification_narrow_by_topic";
        var link_text = i18n.t("Narrow to __- message_recipient__",
                               {message_recipient: get_message_header(message)});

        exports.notify_above_composebox(reason, link_class, link_msg_id, link_text);
    });
};

// for callback when we have to check with the server if a message should be in
// the current_msg_list (!can_apply_locally; a.k.a. "a search").
exports.notify_messages_outside_current_search = function (messages) {
    _.each(messages, function (message) {
        if (!people.is_current_user(message.sender_email)) {
            return;
        }
        var link_text = i18n.t("Narrow to __- message_recipient__",
                               {message_recipient: get_message_header(message)});
        exports.notify_above_composebox(i18n.t("Sent! Your recent message is outside the current search."),
                                        "compose_notification_narrow_by_topic",
                                        message.id,
                                        link_text);
    });
};

exports.clear_compose_notifications = function () {
    $('#out-of-view-notification').empty();
    $('#out-of-view-notification').stop(true, true);
    $('#out-of-view-notification').hide();
};

exports.reify_message_id = function (opts) {
    var old_id = opts.old_id;
    var new_id = opts.new_id;

    // If a message ID that we're currently storing (as a link) has changed,
    // update that link as well
    _.each($('#out-of-view-notification a'), function (e) {
        var elem = $(e);
        var msgid = elem.data('msgid');

        if (msgid === old_id) {
            elem.data('msgid', new_id);
        }
    });
};

exports.register_click_handlers = function () {
    $('#out-of-view-notification').on('click', '.compose_notification_narrow_by_topic', function (e) {
        var msgid = $(e.currentTarget).data('msgid');
        narrow.by_topic(msgid, {trigger: 'compose_notification'});
        e.stopPropagation();
        e.preventDefault();
    });
    $('#out-of-view-notification').on('click', '.compose_notification_scroll_to_message', function (e) {
        var msgid = $(e.currentTarget).data('msgid');
        current_msg_list.select_id(msgid);
        navigate.scroll_to_selected();
        e.stopPropagation();
        e.preventDefault();
    });
    $('#out-of-view-notification').on('click', '.out-of-view-notification-close', function (e) {
        exports.clear_compose_notifications();
        e.stopPropagation();
        e.preventDefault();
    });
};

exports.handle_global_notification_updates = function (notification_name, setting) {
    // Update the global settings checked when determining if we should notify
    // for a given message. These settings do not affect whether or not a
    // particular stream should receive notifications.
    if (settings_notifications.notification_settings.indexOf(notification_name) !== -1) {
        page_params[notification_name] = setting;
    }

    if (notification_name === "notification_sound") {
        // Change the sound source with the new page `notification_sound`.
        update_notification_sound_source();
    }
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = notifications;
}
window.notifications = notifications;
