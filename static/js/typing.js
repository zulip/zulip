var typing = (function () {
var exports = {};

// This module handles the outbound side of typing indicators.
// We detect changes in the compose box and notify the server
// when we are typing.  For the inbound side see typing_events.js.
//
// See docs/subsystems/typing-indicators.md for details on typing indicators.

function send_typing_notification_ajax(user_ids_string, operation) {
    var typing_to = people.user_ids_string_to_emails_string(user_ids_string);
    channel.post({
        url: '/json/typing',
        data: {
            to: typing_to,
            op: operation,
        },
        success: function () {},
        error: function (xhr) {
            blueslip.warn("Failed to send typing event: " + xhr.responseText);
        },
    });
}

function get_user_ids_string() {
    var user_ids_string = compose_pm_pill.get_user_ids_string();

    if (user_ids_string === "") {
        return;
    }
    return user_ids_string;
}

function is_valid_conversation(user_ids_string) {
    // TODO: Check to make sure we're in a PM conversation
    //       with valid emails.
    if (!user_ids_string) {
        return false;
    }

    if (compose_pm_pill.has_unconverted_data()) {
        return true;
    }

    var compose_empty = !compose_state.has_message_content();
    if (compose_empty) {
        return false;
    }

    if (compose_state.get_message_type() !== 'private') {
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

function notify_server_start(user_ids_string) {
    send_typing_notification_ajax(user_ids_string, "start");
}

function notify_server_stop(user_ids_string) {
    send_typing_notification_ajax(user_ids_string, "stop");
}

exports.initialize = function () {
    var worker = {
        get_recipient: get_user_ids_string,
        is_valid_conversation: is_valid_conversation,
        get_current_time: get_current_time,
        notify_server_start: notify_server_start,
        notify_server_stop: notify_server_stop,
    };

    $(document).on('input', '#compose-textarea', function () {
        // If our previous state was no typing notification, send a
        // start-typing notice immediately.
        typing_status.handle_text_input(worker);
    });

    // We send a stop-typing notification immediately when compose is
    // closed/cancelled
    $(document).on('compose_canceled.zulip compose_finished.zulip', function () {
        typing_status.stop(worker);
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = typing;
}
window.typing = typing;
