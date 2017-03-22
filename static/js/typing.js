var typing = (function () {
var exports = {};
// How long before we assume a client has gone away
// and expire its typing status
var TYPING_STARTED_EXPIRY_PERIOD = 15000; // 15s

// Note!: There are also timing constants in typing_status.js
// that make typing indicators work.

var stop_typing_timers = new Dict();

function send_typing_notification_ajax(recipients, operation) {
    channel.post({
        url: '/json/typing',
        data: {
            to: recipients,
            op: operation,
        },
        success: function () {},
        error: function (xhr) {
            blueslip.warn("Failed to send typing event: " + xhr.responseText);
        },
    });
}

function get_recipient() {
    var compose_recipient = compose_state.recipient();
    if (compose_recipient === "") {
        return undefined;
    }
    return compose_recipient;
}

function is_valid_conversation(recipient) {
    // TODO: Check to make sure we're in a PM conversation
    //       with valid emails.
    if (!recipient) {
        return false;
    }

    var compose_empty = !compose_state.has_message_content();
    if (compose_empty) {
        return false;
    }

    if (compose_state.composing() !== 'private') {
        // We only use typing indicators in PMs for now.
        // There was originally some support for having
        // typing indicators related to stream conversations,
        // but the initial rollout led to users being
        // confused by them.  We may revisit this.
        return false;
    }

    return true;
}

function get_current_time() {
    return new Date();
}

function notify_server_start(recipients) {
    send_typing_notification_ajax(recipients, "start");
}

function notify_server_stop(recipients) {
    send_typing_notification_ajax(recipients, "stop");
}

var worker = {
    get_recipient: get_recipient,
    is_valid_conversation: is_valid_conversation,
    get_current_time: get_current_time,
    notify_server_start: notify_server_start,
    notify_server_stop: notify_server_stop,
};

$(document).on('input', '#new_message_content', function () {
    // If our previous state was no typing notification, send a
    // start-typing notice immediately.
    typing_status.handle_text_input(worker);
});

// We send a stop-typing notification immediately when compose is
// closed/cancelled
$(document).on('compose_canceled.zulip compose_finished.zulip', function () {
    typing_status.stop(worker);
});

function get_users_typing_for_narrow() {
    if (!narrow.narrowed_to_pms()) {
        // Narrow is neither pm-with nor is: private
        return [];
    }
    if (narrow.operators()[0].operator === 'pm-with') {
        // Get list of users typing in this conversation
        var narrow_emails_string = narrow.operators()[0].operand;
        // TODO: Create people.emails_strings_to_user_ids.
        var narrow_user_ids_string = people.emails_strings_to_user_ids_string(narrow_emails_string);
        var narrow_user_ids = narrow_user_ids_string.split(',').map(function (user_id_string) {
            return parseInt(user_id_string, 10);
        });
        var group = narrow_user_ids.concat([page_params.user_id]);
        return typing_data.get_group_typists(group);
    }
    // Get all users typing (in all private conversations with current user)
    return typing_data.get_all_typists();
}

function render_notifications_for_narrow() {
    var user_ids = get_users_typing_for_narrow();
    var users_typing = user_ids.map(people.get_person_from_user_id);
    if (users_typing.length === 0) {
        $('#typing_notifications').hide();
    } else {
        $('#typing_notifications').html(templates.render('typing_notifications', {users: users_typing}));
        $('#typing_notifications').show();
    }
}

$(document).on('narrow_activated.zulip', render_notifications_for_narrow);
$(document).on('narrow_deactivated.zulip', render_notifications_for_narrow);

exports.hide_notification = function (event) {
    var recipients = event.recipients.map(function (user) {
        return user.user_id;
    });
    recipients.sort();

    // If there's an existing timer for this typing notifications
    // thread, clear it.
    if (stop_typing_timers[recipients] !== undefined) {
        clearTimeout(stop_typing_timers[recipients]);
        stop_typing_timers[recipients] = undefined;
    }

    var removed = typing_data.remove_typist(recipients, event.sender.user_id);

    if (removed) {
        render_notifications_for_narrow();
    }
};

exports.display_notification = function (event) {
    var recipients = event.recipients.map(function (user) {
        return user.user_id;
    });
    recipients.sort();

    var sender_id = event.sender.user_id;
    event.sender.name = people.get_person_from_user_id(sender_id).full_name;

    typing_data.add_typist(recipients, sender_id);

    render_notifications_for_narrow();
    // If there's an existing timeout for this typing notifications
    // thread, clear it.
    if (stop_typing_timers[recipients] !== undefined) {
        clearTimeout(stop_typing_timers[recipients]);
    }
    // Set a time to expire the data if the sender stops transmitting
    stop_typing_timers[recipients] = setTimeout(function () {
        exports.hide_notification(event);
    }, TYPING_STARTED_EXPIRY_PERIOD);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = typing;
}
