var notifications = (function () {

var exports = {};

var window_has_focus = true;

exports.initialize = function () {
    if (!window.webkitNotifications) {
        return;
    }

    $(window).focus(function () {
        window_has_focus = true;
    }).blur(function () {
        window_has_focus = false;
    });

    $(document).click(function () {
        if (!desktop_notifications_enabled) {
            return;
        }
        if (window.webkitNotifications.checkPermission() !== 0) { // 0 is PERMISSION_ALLOWED
            window.webkitNotifications.requestPermission();
        }
    });
};

function gravatar_url(message) {
    return "https://secure.gravatar.com/avatar/" + message.gravatar_hash +
           "?d=identicon&s=30?stamp=" + ui.get_gravatar_stamp();
}

var notice_memory = {};

function process_message(message) {
    var i, notification_object;
    var key = message.display_reply_to;
    var title = message.sender_full_name;
    var content = $('<div/>').html(message.content).text();
    var other_recipients = message.display_reply_to;
    var msg_count = 1;

    // Remove the sender from the list of other recipients
    other_recipients = other_recipients.replace(", " + message.sender_full_name, "");
    other_recipients = other_recipients.replace(message.sender_full_name + ", ", "");

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

    if (notice_memory[key] !== undefined) {
        msg_count = notice_memory[key].msg_count + 1;
        title = msg_count + " messages from " + title;
        notification_object = notice_memory[key].obj;
        // We must remove the .onclose so that it does not trigger on .cancel
        notification_object.onclose = function () {};
        notification_object.onclick = function () {};
        notification_object.cancel();
    }

    if (message.type === "huddle") {
        // If the message has too many recipients to list them all...
        if (content.length + title.length + other_recipients.length > 230) {
            // Then count how many people are in the conversation and summarize
            // by saying the conversation is with "you and [number] other people"
            other_recipients = other_recipients.replace(/[^,]/g, "").length +
                               " other people";
        }
        title += " (to you and " + other_recipients + ")";
    }

    notice_memory[key] = {
        obj: window.webkitNotifications.createNotification(
                gravatar_url(message), title, content),
        msg_count: msg_count
    };
    notification_object = notice_memory[key].obj;
    notification_object.onclick = function () {
        notification_object.cancel();
        delete notice_memory[key];
    };
    notification_object.onclose = function () {
        delete notice_memory[key];
    };
    notification_object.show();
}

exports.received_messages = function (messages) {
    var i;
    if (!window.webkitNotifications ||
        !desktop_notifications_enabled ||
        window_has_focus) {
        return;
    }

    $.each(messages, function (index, message) {
        if (message.sender_email !== email &&
            (message.type === "personal" || message.type === "huddle")) {
            process_message(message);
        }
    });
};

return exports;

}());
