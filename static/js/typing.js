var typing = (function () {
var exports = {};
// How long before we assume a client has gone away
// and expire its typing status
var TYPING_STARTED_EXPIRY_PERIOD = 15000; // 15s
// How frequently 'still typing' notifications are sent
// to extend the expiry
var TYPING_STARTED_SEND_FREQUENCY = 10000; // 10s
// How long after someone stops editing in the compose box
// do we send a 'stopped typing' notification
var TYPING_STOPPED_WAIT_PERIOD = 5000; // 5s

var current_recipient;
var users_currently_typing = new Dict();

function send_typing_notification_ajax(recipients, operation) {
    channel.post({
        url: '/json/typing',
        data: {
            to: recipients,
            op: operation
        },
        success: function () {},
        error: function (xhr) {
            blueslip.warn("Failed to send typing event: " + xhr.responseText);
        }
    });
}

function check_and_send(operation) {
    if (operation === 'start') {
        if (compose.recipient() && compose.message_content()) {
            if (current_recipient !== undefined && current_recipient !== compose.recipient()) {
                // When the recipient is changed, a stop message is sent to the old recipient
                // before the start message is sent to the new recipient
                send_typing_notification_ajax(current_recipient, 'stop');
            }
            current_recipient = compose.recipient();
            send_typing_notification_ajax(compose.recipient(), operation);
        }
    } else if (operation === 'stop' && current_recipient) {
        send_typing_notification_ajax(current_recipient, operation);
        current_recipient = undefined;
    }
}

function check_and_send_start() {
    check_and_send('start');
}

function get_throttled_function() {
    return _.throttle(check_and_send_start,
        TYPING_STARTED_SEND_FREQUENCY,
        {trailing: false});
}

function check_and_send_stop() {
    check_and_send('stop');
    exports.send_start_notification = get_throttled_function();
    $(document).on('input', '#new_message_content', exports.send_start_notification);
}

exports.send_start_notification = get_throttled_function();
exports.send_stop_notification = _.debounce(check_and_send_stop, TYPING_STOPPED_WAIT_PERIOD);

$(document).on('compose_canceled.zulip', check_and_send_stop);
$(document).on('compose_finished.zulip', check_and_send_stop);
$(document).on('blur', '#new_message_content', check_and_send_stop);
$(document).on('input', '#new_message_content', exports.send_start_notification);
$(document).on('input', '#new_message_content', exports.send_stop_notification);

function full_name(email) {
    return people.get_by_email(email).full_name;
}

function get_users_typing_for_narrow() {
    if (!narrow.narrowed_to_pms()) {
        // Narrow is neither pm-with nor is: private
        return [];
    }
    if (narrow.operators()[0].operator === 'pm-with') {
        // Get list of users typing in this conversation
        var narrow_emails_string = narrow.operators()[0].operand;
        var narrow_user_ids_string = people.emails_strings_to_user_ids_string(narrow_emails_string);
        var narrow_user_ids = narrow_user_ids_string.split(',').map(function (user_id_string) {
            return parseInt(user_id_string, 10);
        });
        var group = narrow_user_ids.concat([page_params.user_id]);
        group.sort();
        return users_currently_typing.setdefault(group, []);
    }
    // Get all users typing (in all private conversations with current user)
    var all_typing_users = [];
    users_currently_typing.each(function (users_typing) {
        all_typing_users = all_typing_users.concat(users_typing);
    });
    return all_typing_users;
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
    if (event.sender.user_id === page_params.user_id) {
        // The typing notification is also sent to the user who is typing
        // In this case the notification is not displayed
        return;
    }
    var recipients = event.recipients.map(function (user) {
        return user.user_id;
    });
    recipients.sort();
    var users_typing = users_currently_typing.get(recipients);
    var i = users_typing.indexOf(event.sender.user_id);
    if (i !== -1) {
        users_typing.splice(i);
    }
    render_notifications_for_narrow();
};

var debounced_hide_notification = _.debounce(exports.hide_notification,
    TYPING_STARTED_EXPIRY_PERIOD);

exports.display_notification = function (event) {
    var recipients = event.recipients.map(function (user) {
        return user.user_id;
    });
    recipients.sort();
    if (event.sender.user_id === page_params.user_id) {
        // The typing notification is also sent to the user who is typing
        // In this case the notification is not displayed
        return;
    }
    event.sender.name = full_name(event.sender.email);
    var users_typing = users_currently_typing.setdefault(recipients, []);
    var i = users_typing.indexOf(event.sender.user_id);
    if (i === -1) {
      // Add sender to list of users currently typing in conversation
      users_typing.push(event.sender.user_id);
    }
    render_notifications_for_narrow();
    debounced_hide_notification(event);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = typing;
}
