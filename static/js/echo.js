var echo = (function () {

var exports = {};

var waiting_for_id = {};
var waiting_for_ack = {};
var home_view_loaded = false;

function resend_message(message, row) {
    message.content = message.raw_content;
    var retry_spinner = row.find('.refresh-failed-message');
    retry_spinner.toggleClass('rotating', true);
    // Always re-set queue_id if we've gotten a new one
    // since the time when the message object was initially created
    message.queue_id = page_params.queue_id;
    var start_time = new Date();
    compose.transmit_message(message, function success(data) {
        retry_spinner.toggleClass('rotating', false);

        var message_id = data.id;

        retry_spinner.toggleClass('rotating', false);
        compose.send_message_success(message.local_id, message_id, start_time, true);

        // Resend succeeded, so mark as no longer failed
        message_store.get(message_id).failed_request = false;
        ui.show_failed_message_success(message_id);
    }, function error(response) {
        exports.message_send_error(message.local_id, response);
        retry_spinner.toggleClass('rotating', false);
        blueslip.log("Manual resend of message failed");
    });
}

function truncate_precision(float) {
    return parseFloat(float.toFixed(3));
}

function get_next_local_id() {
    var local_id_increment = 0.01;
    var latest = page_params.max_message_id;
    if (typeof message_list.all !== 'undefined' && message_list.all.last() !== undefined) {
        latest = message_list.all.last().id;
    }
    latest = Math.max(0, latest);
    return truncate_precision(latest + local_id_increment);
}

function insert_local_message(message_request, local_id) {
    // Shallow clone of message request object that is turned into something suitable
    // for zulip.js:add_message
    // Keep this in sync with changes to compose.create_message_object
    var message = $.extend({}, message_request);

    // Locally delivered messages cannot be unread (since we sent them), nor
    // can they alert the user.
    message.flags = ['read']; // we may add more flags later

    message.raw_content = message.content;

    // NOTE: This will parse synchronously. We're not using the async pipeline
    markdown.apply_markdown(message);

    message.content_type = 'text/html';
    message.sender_email = people.my_current_email();
    message.sender_full_name = people.my_full_name();
    message.avatar_url = page_params.avatar_url;
    message.timestamp = new XDate().getTime() / 1000;
    message.local_id = local_id;
    message.id = message.local_id;
    markdown.add_message_flags(message);
    markdown.add_subject_links(message);

    waiting_for_id[message.local_id] = message;
    waiting_for_ack[message.local_id] = message;

    if (message.type === 'stream') {
        message.display_recipient = message.stream;
    } else {
        // Build a display recipient with the full names of each
        // recipient.  Note that it's important that use
        // util.extract_pm_recipients, which filters out any spurious
        // ", " at the end of the recipient list
        var emails = util.extract_pm_recipients(message_request.private_message_recipient);
        message.display_recipient = _.map(emails, function (email) {
            email = email.trim();
            var person = people.get_by_email(email);
            if (person === undefined) {
                // For unknown users, we return a skeleton object.
                return {email: email, full_name: email,
                        unknown_local_echo_user: true};
            }
            // NORMAL PATH
            return person;
        });
    }

    // It is a little bit funny to go through the message_events
    // codepath, but it's sort of the idea behind local echo that
    // we are simulating server events before they actually arrive.
    message_events.insert_new_messages([message], local_id);
    return message.local_id;
}

exports.try_deliver_locally = function try_deliver_locally(message_request) {
    var next_local_id = get_next_local_id();
    if (next_local_id % 1 === 0) {
        blueslip.error("Incremented local id to next integer---100 local messages queued");
        return undefined;
    }

    if (markdown.contains_bugdown(message_request.content)) {
        return undefined;
    }

    if (narrow_state.active() && !narrow_state.filter().can_apply_locally()) {
        return undefined;
    }

    return insert_local_message(message_request, next_local_id);
};

exports.edit_locally = function edit_locally(message, raw_content, new_topic) {
    message.raw_content = raw_content;
    if (new_topic !== undefined) {
        stream_data.process_message_for_recent_topics(message, true);
        message.subject = new_topic;
        stream_data.process_message_for_recent_topics(message);
    }

    markdown.apply_markdown(message);

    // We don't handle unread counts since local messages must be sent by us

    home_msg_list.view.rerender_messages([message]);
    if (current_msg_list === message_list.narrowed) {
        message_list.narrowed.view.rerender_messages([message]);
    }
    stream_list.update_streams_sidebar();
    pm_list.update_private_messages();
};

exports.reify_message_id = function reify_message_id(local_id, server_id) {
    var message = waiting_for_id[local_id];
    delete waiting_for_id[local_id];

    // reify_message_id is called both on receiving a self-sent message
    // from the server, and on receiving the response to the send request
    // Reification is only needed the first time the server id is found
    if (message === undefined) {
        return;
    }

    message.id = server_id;
    delete message.local_id;

    // We have the real message ID  for this message
    $(document).trigger($.Event('message_id_changed', {old_id: local_id, new_id: server_id}));
};

exports.process_from_server = function process_from_server(messages) {
    var updated = false;
    var locally_processed_ids = [];
    var msgs_to_rerender = [];
    messages = _.filter(messages, function (message) {
        // In case we get the sent message before we get the send ACK, reify here
        exports.reify_message_id(message.local_id, message.id);

        var client_message = waiting_for_ack[message.local_id];
        if (client_message !== undefined) {
            if (client_message.content !== message.content) {
                client_message.content = message.content;
                updated = true;
                compose.mark_rendered_content_disparity(message.id, true);
            }
            msgs_to_rerender.push(client_message);
            locally_processed_ids.push(client_message.id);
            compose.report_as_received(client_message);
            delete waiting_for_ack[client_message.id];
            return false;
        }
        return true;
    });

    if (updated) {
        home_msg_list.view.rerender_messages(msgs_to_rerender);
        if (current_msg_list === message_list.narrowed) {
            message_list.narrowed.view.rerender_messages(msgs_to_rerender);
        }
    } else {
        _.each(locally_processed_ids, function (id) {
            ui.show_local_message_arrived(id);
        });
    }
    return messages;
};

exports.message_send_error = function message_send_error(local_id, error_response) {
    // Error sending message, show inline
    message_store.get(local_id).failed_request = true;
    ui.show_message_failed(local_id, error_response);
};

function abort_message(message) {
    // Remove in all lists in which it exists
    _.each([message_list.all, home_msg_list, current_msg_list], function (msg_list) {
        msg_list.remove_and_rerender([message]);
    });
}

function edit_failed_message(message) {
    message_edit.start_local_failed_edit(current_msg_list.get_row(message.local_id), message);
}


$(function () {
    function on_failed_action(action, callback) {
        $("#main_div").on("click", "." + action + "-failed-message", function (e) {
            e.stopPropagation();
            popovers.hide_all();
            var row = $(this).closest(".message_row");
            var message_id = rows.id(row);
            // Message should be waiting for ack and only have a local id,
            // otherwise send would not have failed
            var message = waiting_for_ack[message_id];
            if (message === undefined) {
                blueslip.warn("Got resend or retry on failure request but did not find message in ack list " + message_id);
                return;
            }
            callback(message, row);
        });
    }

    on_failed_action('remove', abort_message);
    on_failed_action('refresh', resend_message);
    on_failed_action('edit', edit_failed_message);

    $(document).on('home_view_loaded.zulip', function () {
        home_view_loaded = true;
    });
});

$(document).on('socket_loaded_requests.zulip', function (event, data) {
    var msgs_to_insert = [];

    var next_local_id = get_next_local_id();
    _.each(data.requests, function (socket_msg) {
        var msg = socket_msg.msg;
        // Check for any message objects, then insert them locally
        if (msg.stream === undefined || msg.local_id === undefined) {
            return;
        }
        msg.local_id = next_local_id;
        msg.queue_id = page_params.queue_id;

        next_local_id = truncate_precision(next_local_id + 0.01);
        msgs_to_insert.push(msg);
    });

    function echo_pending_messages() {
        _.each(msgs_to_insert, function (msg) {
            insert_local_message(msg, msg.local_id);
        });
    }
    if (home_view_loaded) {
        echo_pending_messages();
    } else {
        $(document).on('home_view_loaded.zulip', function () {
            echo_pending_messages();
        });
    }
});

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = echo;
}
