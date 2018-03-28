var echo = (function () {

var exports = {};

var waiting_for_id = {};
var waiting_for_ack = {};

function resend_message(message, row) {
    message.content = message.raw_content;
    var retry_spinner = row.find('.refresh-failed-message');
    retry_spinner.toggleClass('rotating', true);

    // Always re-set queue_id if we've gotten a new one
    // since the time when the message object was initially created
    message.queue_id = page_params.queue_id;

    var local_id = message.local_id;

    function on_success(data) {
        var message_id = data.id;
        var locally_echoed = true;

        retry_spinner.toggleClass('rotating', false);

        compose.send_message_success(local_id, message_id, locally_echoed);

        // Resend succeeded, so mark as no longer failed
        message_store.get(message_id).failed_request = false;
        ui.show_failed_message_success(message_id);
    }

    function on_error(response) {
        exports.message_send_error(local_id, response);
        retry_spinner.toggleClass('rotating', false);
        blueslip.log("Manual resend of message failed");
    }

    sent_messages.start_resend(local_id);
    transmit.send_message(message, on_success, on_error);
}

function truncate_precision(float) {
    return parseFloat(float.toFixed(3));
}

var get_next_local_id = (function () {

    var already_used = {};

    return function () {
        var local_id_increment = 0.01;
        var latest = page_params.max_message_id;
        if (typeof message_list.all !== 'undefined' && message_list.all.last() !== undefined) {
            latest = message_list.all.last().id;
        }
        latest = Math.max(0, latest);
        var next_local_id = truncate_precision(latest + local_id_increment);

        if (already_used[next_local_id]) {
            // If our id is already used, it is probably an edge case like we had
            // to abort a very recent message.
            blueslip.warn("We don't reuse ids for local echo.");
            return;
        }

        if (next_local_id % 1 > local_id_increment * 5) {
            blueslip.warn("Turning off local echo for this message to let host catch up");
            return;
        }

        if (next_local_id % 1 === 0) {
            // The logic to stop at 0.05 should prevent us from ever wrapping around
            // to the next integer.
            blueslip.error("Programming error");
            return;
        }

        already_used[next_local_id] = true;

        return next_local_id;
    };
}());

function insert_local_message(message_request, local_id) {
    // Shallow clone of message request object that is turned into something suitable
    // for zulip.js:add_message
    // Keep this in sync with changes to compose.create_message_object
    var message = $.extend({}, message_request);

    // Locally delivered messages cannot be unread (since we sent them), nor
    // can they alert the user.
    message.unread = false;

    message.raw_content = message.content;

    // NOTE: This will parse synchronously. We're not using the async pipeline
    markdown.apply_markdown(message);

    message.content_type = 'text/html';
    message.sender_email = people.my_current_email();
    message.sender_full_name = people.my_full_name();
    message.avatar_url = page_params.avatar_url;
    message.timestamp = new XDate().getTime() / 1000;
    message.local_id = local_id;
    message.locally_echoed = true;
    message.id = message.local_id;
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
    message_events.insert_new_messages([message], true);
    return message.local_id;
}

exports.try_deliver_locally = function try_deliver_locally(message_request) {
    if (markdown.contains_backend_only_syntax(message_request.content)) {
        return;
    }

    if (narrow_state.active() && !narrow_state.filter().can_apply_locally()) {
        return;
    }

    var next_local_id = get_next_local_id();

    if (!next_local_id) {
        // This can happen for legit reasons.
        return;
    }

    return insert_local_message(message_request, next_local_id);
};

exports.edit_locally = function edit_locally(message, raw_content, new_topic) {
    message.raw_content = raw_content;
    if (new_topic !== undefined) {
        topic_data.remove_message({
            stream_id: message.stream_id,
            topic_name: message.subject,
        });

        message.subject = new_topic;

        topic_data.add_message({
            stream_id: message.stream_id,
            topic_name: message.subject,
            message_id: message.id,
        });
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
    message.locally_echoed = false;

    var opts = {old_id: local_id, new_id: server_id};

    message_store.reify_message_id(opts);
    notifications.reify_message_id(opts);
};

exports.process_from_server = function process_from_server(messages) {
    var msgs_to_rerender = [];
    var non_echo_messages = [];

    _.each(messages, function (message) {
        // In case we get the sent message before we get the send ACK, reify here

        var client_message = waiting_for_ack[message.local_id];

        if (client_message === undefined) {
            // For messages that weren't locally echoed, we go through
            // the "main" codepath that doesn't have to id reconciliation.
            // We simply return non-echo messages to our caller.
            non_echo_messages.push(message);
            return;
        }

        exports.reify_message_id(message.local_id, message.id);

        if (client_message.content !== message.content) {
            client_message.content = message.content;
            sent_messages.mark_disparity(message.local_id);
        }

        message_store.update_booleans(client_message, message.flags);

        // We don't try to highlight alert words locally, so we have to
        // do it now.  (Note that we will indeed highlight alert words in
        // messages that we sent to ourselves, since we might want to test
        // that our alert words are set up correctly.)
        alert_words.process_message(client_message);

        // Previously, the message had the "local echo" timestamp set
        // by the browser; if there was some round-trip delay to the
        // server, the actual server-side timestamp could be slightly
        // different.  This corrects the frontend timestamp to match
        // the backend.
        client_message.timestamp = message.timestamp;

        msgs_to_rerender.push(client_message);
        delete waiting_for_ack[client_message.id];
    });

    if (msgs_to_rerender.length > 0) {
        // In theory, we could just rerender messages where there were
        // changes in either the rounded timestamp we display or the
        // message content, but in practice, there's no harm to just
        // doing it unconditionally.
        home_msg_list.view.rerender_messages(msgs_to_rerender);
        if (current_msg_list === message_list.narrowed) {
            message_list.narrowed.view.rerender_messages(msgs_to_rerender);
        }
    }

    return non_echo_messages;
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
});

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = echo;
}
