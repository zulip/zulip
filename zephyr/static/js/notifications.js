var notifications = (function () {

var exports = {};

var notice_memory = {};
var window_has_focus = true;
var asked_permission_already = false;
var names;
var supports_sound;

function browser_desktop_notifications_on () {
    return (window.webkitNotifications &&
            // Firefox on Ubuntu claims to do webkitNotifications but its notifications are terrible
            $.browser.webkit &&
            // 0 is PERMISSION_ALLOWED
            window.webkitNotifications.checkPermission() === 0) ||
        // window.bridge is the desktop client
        (window.bridge !== undefined);
}

exports.initialize = function () {
    $(window).focus(function () {
        window_has_focus = true;

        $.each(notice_memory, function (index, notice_mem_entry) {
           notice_mem_entry.obj.cancel();
        });

        // Update many places on the DOM to reflect unread
        // counts.
        process_visible_unread_messages();
    }).blur(function () {
        window_has_focus = false;
    });

    if (!window.webkitNotifications) {
        return;
    }

    $(document).click(function () {
        if (!page_params.desktop_notifications_enabled || asked_permission_already) {
            return;
        }
        if (window.webkitNotifications.checkPermission() !== 0) { // 0 is PERMISSION_ALLOWED
            window.webkitNotifications.requestPermission(function () {});
            asked_permission_already = true;
        }
    });
    var audio = $("<audio>");
    if (window.bridge !== undefined) {
        supports_sound = true;
    } else if (audio[0].canPlayType === undefined) {
        supports_sound = false;
    } else {
        supports_sound = true;
        $("#notifications-area").append(audio);
        if (audio[0].canPlayType('audio/ogg; codecs="vorbis"')) {
            audio.append($("<source>").attr("type", "audio/ogg")
                                      .attr("loop", "yes")
                                      .attr("src", "/static/audio/humbug.ogg"));
        } else {
            audio.append($("<source>").attr("type", "audio/mpeg")
                                      .attr("loop", "yes")
                                      .attr("src", "/static/audio/humbug.mp3"));
        }
    }
};

exports.update_title_count = function (new_message_count) {
    // Update window title and favicon to reflect unread messages in current view
    var n;

    var new_title = (new_message_count ? ("(" + new_message_count + ") ") : "")
        + page_params.domain + " - Humbug";

    if (document.title === new_title) {
        return;
    }

    document.title = new_title;

    // IE doesn't support PNG favicons, *shrug*
    if (! $.browser.msie) {
        // Indicate the message count in the favicon
        if (new_message_count) {
            // Make sure we're working with a number, as a defensive programming
            // measure.  And we don't have images above 99, so display those as
            // 'infinite'.
            n = (+new_message_count);
            if (n > 99)
                n = 'infinite';

            util.set_favicon('/static/images/favicon/favicon-'+n+'.png');
        } else {
            util.set_favicon('/static/favicon.ico?v=2');
        }
    }

    if (window.bridge !== undefined) {
        // We don't use 'n' because we want the exact count. The bridge handles
        // which icon to show.
        window.bridge.updateCount(new_message_count);
    }
};

exports.update_pm_count = function (new_pm_count) {
    if (window.bridge !== undefined && window.bridge.updatePMCount !== undefined) {
        window.bridge.updatePMCount(new_pm_count);
    }
};

exports.window_has_focus = function () {
    return window_has_focus;
};

function process_desktop_notification(message) {
    var i, notification_object, key;
    var title = message.sender_full_name;
    var content = $('<div/>').html(message.content).text();
    var other_recipients;
    var msg_count = 1;

    if (message.type === "private") {
        key = message.display_reply_to;
        other_recipients = message.display_reply_to;
        // Remove the sender from the list of other recipients
        other_recipients = other_recipients.replace(", " + message.sender_full_name, "");
        other_recipients = other_recipients.replace(message.sender_full_name + ", ", "");
    } else {
        key = message.sender_full_name + " to " +
              message.stream + " > " + message.subject;
    }

    if (content.length > 150) {
        // Truncate content at a word boundary
        for (i = 150; i > 0; i--) {
            if (content[i] === ' ') {
                break;
            }
        }
        content = content.substring(0, i);
        content += " [...]";
    }

    if (window.bridge === undefined && notice_memory[key] !== undefined) {
        msg_count = notice_memory[key].msg_count + 1;
        title = msg_count + " messages from " + title;
        notification_object = notice_memory[key].obj;
        // We must remove the .onclose so that it does not trigger on .cancel
        notification_object.onclose = function () {};
        notification_object.onclick = function () {};
        notification_object.cancel();
    }

    if (message.type === "private" && message.display_recipient.length > 2) {
        // If the message has too many recipients to list them all...
        if (content.length + title.length + other_recipients.length > 230) {
            // Then count how many people are in the conversation and summarize
            // by saying the conversation is with "you and [number] other people"
            other_recipients = other_recipients.replace(/[^,]/g, "").length +
                               " other people";
        }
        title += " (to you and " + other_recipients + ")";
    }
    if (message.type === "stream") {
        title += " (to " + message.stream + " > " + message.subject + ")";
    }

    if (window.bridge === undefined) {
        var icon_url = ui.small_avatar_url(message);
        notice_memory[key] = {
            obj: window.webkitNotifications.createNotification(
                    icon_url, title, content),
            msg_count: msg_count
        };
        notification_object = notice_memory[key].obj;
        notification_object.onclick = function () {
            notification_object.cancel();
            window.focus();
        };
        notification_object.onclose = function () {
            delete notice_memory[key];
        };
        notification_object.show();
    } else {
        // Shunt the message along to the desktop client
        window.bridge.desktopNotification(title, content);
    }
}

exports.speaking_at_me = function (message) {
    if (message === undefined) {
        return false;
    }

    return message.mentioned;
};

function message_is_notifiable(message) {
    // based purely on message contents, can we notify the user about the message?
    return (message.type === "private" ||
            exports.speaking_at_me(message) ||
           (message.type === "stream" &&
            subs.receives_notifications(message.stream)));
}

exports.received_messages = function (messages) {
    var i;

    $.each(messages, function (index, message) {
        // We send notifications for messages which the user has
        // configured as notifiable, as long as they haven't been
        // marked as read by process_visible_unread_messages
        // (which occurs if the message arrived onscreen while the
        // window had focus).
        if (!(message_is_notifiable(message) && unread.message_unread(message))) {
            return;
        }
        if (page_params.desktop_notifications_enabled &&
            browser_desktop_notifications_on()) {
            process_desktop_notification(message);
        }
        if (page_params.sounds_enabled && supports_sound) {
            if (window.bridge !== undefined) {
                window.bridge.bell();
            } else {
                $("#notifications-area").find("audio")[0].play();
            }
        }
    });
};

$(function () {
    // Shim for Cocoa WebScript exporting top-level JS
    // objects instead of window.foo objects
    if (typeof(bridge) !== 'undefined' && window.bridge === undefined) {
        window.bridge = bridge;
    }
});

return exports;

}());
