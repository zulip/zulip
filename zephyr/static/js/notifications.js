var notifications = (function () {

var exports = {};

var notice_memory = {};
var window_has_focus = true;
var new_message_count = 0;
var asked_permission_already = false;
var names;

function browser_desktop_notifications_on () {
    return (window.webkitNotifications &&
            // Firefox on Ubuntu claims to do webkitNotifications but its notifications are terrible
            $.browser.webkit &&
            // 0 is PERMISSION_ALLOWED
            window.webkitNotifications.checkPermission() === 0);
}

exports.initialize = function () {
    names = fullname.toLowerCase().split(" ");
    names.push(email.split("@")[0].toLowerCase());
    names.push("all");
    names.push("everyone");
    names.push("<strong>" + fullname.toLowerCase() + "</strong>");

    $(window).focus(function () {
        window_has_focus = true;
        if (new_message_count !== 0) {
            Notificon("");
            new_message_count = 0;
            document.title = domain + " - Humbug";
        }

        $.each(notice_memory, function (index, notice_mem_entry) {
           notice_mem_entry.obj.cancel();
        });
    }).blur(function () {
        window_has_focus = false;
    }).mouseover(function () {
        if (new_message_count !== 0) {
            Notificon("");
            new_message_count = 0;
            document.title = domain + " - Humbug";
        }
    });

    if (!window.webkitNotifications) {
        return;
    }

    $(document).click(function () {
        if (!desktop_notifications_enabled || asked_permission_already) {
            return;
        }
        if (window.webkitNotifications.checkPermission() !== 0) { // 0 is PERMISSION_ALLOWED
            window.webkitNotifications.requestPermission();
            asked_permission_already = true;
        }
    });
};

function gravatar_url(message) {
    return "https://secure.gravatar.com/avatar/" + message.gravatar_hash +
           "?d=identicon&s=30?stamp=" + ui.get_gravatar_stamp();
}

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
              message.display_recipient + " | " + message.subject;
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

    if (notice_memory[key] !== undefined) {
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
        title += " (to " + message.display_recipient + " | " + message.subject + ")";
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

function speaking_at_me(message) {
    var content_lc = message.content.toLowerCase();
    var found_match = false, indexof, after_name, after_atname;
    var punctuation = /[\.,-\/#!$%\^&\*;:{}=\-_`~()\+\?\[\]\s<>]/;

    if (domain === "mit.edu") {
        return false;
    }

    $.each(names, function (index, name) {
        indexof = content_lc.indexOf(name.toLowerCase());
        if (indexof === -1) {
            // If there is no match, we don't need after_name
            after_name = undefined;
        } else if (indexof + name.length >= content_lc.length) {
            // If the @name is at the end of the string, that's OK,
            // so we set after_name to " " so that the code below
            // will identify a match
            after_name = " ";
        } else {
            after_name = content_lc.charAt(indexof + name.length);
        }
        if ((indexof === 0 &&
             after_name.match(punctuation) !== null) ||
            (indexof > 0 && content_lc.charAt(indexof-1) === "@" &&
             after_name.match(punctuation) !== null)) {
                found_match = true;
                return false;
        }
    });

    return found_match;
}

exports.received_messages = function (messages) {
    var i, title_needs_update = false;
    if (window_has_focus) {
        return;
    }

    $.each(messages, function (index, message) {
        if (message.sender_email !== email) {
            new_message_count++;
            title_needs_update = true;

            if (desktop_notifications_enabled &&
                browser_desktop_notifications_on() &&
                (message.type === "private" ||
                speaking_at_me(message))) {
                process_desktop_notification(message);
            }
        }
    });

    if (title_needs_update) {
        document.title = "(" + new_message_count + ") " + domain + " - Humbug";
        Notificon(new_message_count);
    }
};

return exports;

}());
