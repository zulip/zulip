// Docs: https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html

const waiting_for_id = {};
let waiting_for_ack = {};

function resend_message(message, row) {
    message.content = message.raw_content;
    const retry_spinner = row.find('.refresh-failed-message');
    retry_spinner.toggleClass('rotating', true);

    // Always re-set queue_id if we've gotten a new one
    // since the time when the message object was initially created
    message.queue_id = page_params.queue_id;

    const local_id = message.local_id;

    function on_success(data) {
        const message_id = data.id;
        const locally_echoed = true;

        retry_spinner.toggleClass('rotating', false);

        compose.send_message_success(local_id, message_id, locally_echoed);

        // Resend succeeded, so mark as no longer failed
        message_store.get(message_id).failed_request = false;
        ui.show_failed_message_success(message_id);
    }

    function on_error(response) {
        exports.message_send_error(local_id, response);
        setTimeout(function () {
            retry_spinner.toggleClass('rotating', false);
        }, 300);
        blueslip.log("Manual resend of message failed");
    }

    sent_messages.start_resend(local_id);
    transmit.send_message(message, on_success, on_error);
}

exports.build_display_recipient = function (message) {
    if (message.type === 'stream') {
        return message.stream;
    }

    // Build a display recipient with the full names of each
    // recipient.  Note that it's important that use
    // util.extract_pm_recipients, which filters out any spurious
    // ", " at the end of the recipient list
    const emails = util.extract_pm_recipients(message.private_message_recipient);

    let me_in_display_recipients = false;
    const display_recipient = _.map(emails, function (email) {
        email = email.trim();
        const person = people.get_by_email(email);
        if (person === undefined) {
            // For unknown users, we return a skeleton object.
            //
            // This allows us to support zephyr mirroring situations
            // where the server might dynamically create users in
            // response to messages being sent to their email address.
            //
            // TODO: It might be cleaner for the webapp for such
            // dynamic user creation to happen inside a separate API
            // call when the pill is constructed, and then enforcing
            // the requirement that we have an actual user object in
            // `people.js` when sending messages.
            return {
                email: email,
                full_name: email,
                unknown_local_echo_user: true,
            };
        }

        if (people.is_my_user_id(person.user_id)) {
            me_in_display_recipients = true;
        }

        // NORMAL PATH
        //
        // This should match the format of display_recipient
        // objects generated by the backend code in models.py,
        // which is why we create a new object with a `.id` field
        // rather than a `.user_id` field.
        return {
            id: person.user_id,
            email: person.email,
            full_name: person.full_name,
        };
    });

    if (!me_in_display_recipients) {
        // Ensure that the current user is included in
        // display_recipient for group PMs.
        display_recipient.push({
            id: message.sender_id,
            email: message.sender_email,
            full_name: message.sender_full_name,
        });
    }
    return display_recipient;
};

exports.insert_local_message = function (message_request, local_id) {
    // Shallow clone of message request object that is turned into something suitable
    // for zulip.js:add_message
    // Keep this in sync with changes to compose.create_message_object
    const message = $.extend({}, message_request);

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
    message.timestamp = local_message.now();
    message.local_id = local_id;
    message.locally_echoed = true;
    message.id = message.local_id;
    markdown.add_topic_links(message);

    waiting_for_id[message.local_id] = message;
    waiting_for_ack[message.local_id] = message;

    message.display_recipient = echo.build_display_recipient(message);
    local_message.insert_message(message);
    return message.local_id.toString();
};

exports.is_slash_command = function (content) {
    return !content.startsWith('/me') && content.startsWith('/');
};


exports.try_deliver_locally = function try_deliver_locally(message_request) {
    if (markdown.contains_backend_only_syntax(message_request.content)) {
        return;
    }

    if (narrow_state.active() && !narrow_state.filter().can_apply_locally()) {
        return;
    }

    if (exports.is_slash_command(message_request.content)) {
        return;
    }

    const next_local_id = local_message.get_next_id();

    if (!next_local_id) {
        // This can happen for legit reasons.
        return;
    }

    return exports.insert_local_message(message_request, next_local_id);
};

exports.edit_locally = function edit_locally(message, request) {
    // Responsible for doing the rendering work of locally editing the
    // content ofa message.  This is used in several code paths:
    // * Editing a message where a message was locally echoed but
    //   it got an error back from the server
    // * Locally echoing any content-only edits to fully sent messages
    // * Restoring the original content should the server return an
    //   error after having locally echoed content-only messages.
    // The details of what should be changed are encoded in the request.
    const raw_content = request.raw_content;
    const message_content_edited = raw_content !== undefined && message.raw_content !== raw_content;

    if (request.new_topic !== undefined) {
        const new_topic = request.new_topic;
        topic_data.remove_message({
            stream_id: message.stream_id,
            topic_name: util.get_message_topic(message),
        });

        util.set_message_topic(message, new_topic);

        topic_data.add_message({
            stream_id: message.stream_id,
            topic_name: util.get_message_topic(message),
            message_id: message.id,
        });
    }

    if (message_content_edited) {
        message.raw_content = raw_content;
        if (request.content !== undefined) {
            // This happens in the code path where message editing
            // failed and we're trying to undo the local echo.  We use
            // the saved content and flags rather than rendering; this
            // is important in case
            // markdown.contains_backend_only_syntax(message) is true.
            message.content = request.content;
            message.mentioned = request.mentioned;
            message.mentioned_me_directly = request.mentioned_me_directly;
            message.alerted = request.alerted;
        } else {
            // Otherwise, we markdown-render the message; this resets
            // all flags, so we need to restore those flags that are
            // properties of how the user has interacted with the
            // message, and not its rendering.
            markdown.apply_markdown(message);
            if (request.starred !== undefined) {
                message.starred = request.starred;
            }
            if (request.historical !== undefined) {
                message.historical = request.historical;
            }
            if (request.collapsed !== undefined) {
                message.collapsed = request.collapsed;
            }
        }
    }

    // We don't have logic to adjust unread counts, because message
    // reaching this code path must either have been sent by us or the
    // topic isn't being edited, so unread counts can't have changed.

    home_msg_list.view.rerender_messages([message]);
    if (current_msg_list === message_list.narrowed) {
        message_list.narrowed.view.rerender_messages([message]);
    }
    stream_list.update_streams_sidebar();
    pm_list.update_private_messages();
};

exports.reify_message_id = function reify_message_id(local_id, server_id) {
    const message = waiting_for_id[local_id];
    delete waiting_for_id[local_id];

    // reify_message_id is called both on receiving a self-sent message
    // from the server, and on receiving the response to the send request
    // Reification is only needed the first time the server id is found
    if (message === undefined) {
        return;
    }

    message.id = server_id;
    message.locally_echoed = false;

    const opts = {old_id: parseFloat(local_id), new_id: server_id};

    message_store.reify_message_id(opts);
    notifications.reify_message_id(opts);
};

exports.process_from_server = function process_from_server(messages) {
    const msgs_to_rerender = [];
    const non_echo_messages = [];

    _.each(messages, function (message) {
        // In case we get the sent message before we get the send ACK, reify here

        const client_message = waiting_for_ack[message.local_id];
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

        util.set_topic_links(client_message, util.get_topic_links(message));
        client_message.is_me_message = message.is_me_message;
        client_message.submessages = message.submessages;

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

exports._patch_waiting_for_awk = function _patch_waiting_for_awk(data) {
    // Only for testing
    waiting_for_ack = data;
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

exports.initialize = function () {
    function on_failed_action(action, callback) {
        $("#main_div").on("click", "." + action + "-failed-message", function (e) {
            e.stopPropagation();
            popovers.hide_all();
            const row = $(this).closest(".message_row");
            const message_id = rows.id(row);
            // Message should be waiting for ack and only have a local id,
            // otherwise send would not have failed
            const message = waiting_for_ack[message_id];
            if (message === undefined) {
                blueslip.warn("Got resend or retry on failure request but did not find message in ack list " + message_id);
                return;
            }
            callback(message, row);
        });
    }

    on_failed_action('remove', abort_message);
    on_failed_action('refresh', resend_message);
};

window.echo = exports;
