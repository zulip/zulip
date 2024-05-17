import $ from "jquery";

import * as alert_words from "./alert_words";
import {all_messages_data} from "./all_messages_data";
import * as blueslip from "./blueslip";
import * as compose_notifications from "./compose_notifications";
import * as compose_ui from "./compose_ui";
import * as local_message from "./local_message";
import * as markdown from "./markdown";
import * as message_lists from "./message_lists";
import * as message_live_update from "./message_live_update";
import * as message_store from "./message_store";
import * as people from "./people";
import * as pm_list from "./pm_list";
import * as recent_view_data from "./recent_view_data";
import * as rows from "./rows";
import * as sent_messages from "./sent_messages";
import {current_user} from "./state_data";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as stream_topic_history from "./stream_topic_history";
import * as util from "./util";

// Docs: https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html

const waiting_for_id = new Map();
let waiting_for_ack = new Map();

// These retry spinner functions return true if and only if the
// spinner already is in the requested state, which can be used to
// avoid sending duplicate requests.
function show_retry_spinner($row) {
    const $retry_spinner = $row.find(".refresh-failed-message");

    if (!$retry_spinner.hasClass("rotating")) {
        $retry_spinner.toggleClass("rotating", true);
        return false;
    }
    return true;
}

function hide_retry_spinner($row) {
    const $retry_spinner = $row.find(".refresh-failed-message");

    if ($retry_spinner.hasClass("rotating")) {
        $retry_spinner.toggleClass("rotating", false);
        return false;
    }
    return true;
}

function show_message_failed(message_id, failed_msg) {
    // Failed to send message, so display inline retry/cancel
    message_live_update.update_message_in_all_views(message_id, ($row) => {
        $row.find(".slow-send-spinner").addClass("hidden");
        const $failed_div = $row.find(".message_failed");
        $failed_div.toggleClass("hide", false);
        $failed_div.find(".failed_text").attr("title", failed_msg);
    });
}

function show_failed_message_success(message_id) {
    // Previously failed message succeeded
    message_live_update.update_message_in_all_views(message_id, ($row) => {
        $row.find(".message_failed").toggleClass("hide", true);
    });
}

function failed_message_success(message_id) {
    message_store.get(message_id).failed_request = false;
    show_failed_message_success(message_id);
}

function resend_message(message, $row, {on_send_message_success, send_message}) {
    message.content = message.raw_content;
    if (show_retry_spinner($row)) {
        // retry already in in progress
        return;
    }

    message.resend = true;

    function on_success(data) {
        const message_id = data.id;
        message.locally_echoed = true;

        hide_retry_spinner($row);

        on_send_message_success(message, data);

        // Resend succeeded, so mark as no longer failed
        failed_message_success(message_id);
    }

    function on_error(response, _server_error_code) {
        message_send_error(message.id, response);
        setTimeout(() => {
            hide_retry_spinner($row);
        }, 300);
        blueslip.log("Manual resend of message failed");
    }

    send_message(message, on_success, on_error);
}

export function build_display_recipient(message) {
    if (message.type === "stream") {
        return stream_data.get_stream_name_from_id(message.stream_id);
    }

    // Build a display recipient with the full names of each
    // recipient.  Note that it's important that use
    // util.extract_pm_recipients, which filters out any spurious
    // ", " at the end of the recipient list
    const emails = util.extract_pm_recipients(message.private_message_recipient);

    let sender_in_display_recipients = false;
    const display_recipient = emails.map((email) => {
        email = email.trim();
        const person = people.get_by_email(email);
        if (person === undefined) {
            // For unknown users, we return a skeleton object.
            //
            // This allows us to support zephyr mirroring situations
            // where the server might dynamically create users in
            // response to messages being sent to their email address.
            //
            // TODO: It might be cleaner for the web app for such
            // dynamic user creation to happen inside a separate API
            // call when the pill is constructed, and then enforcing
            // the requirement that we have an actual user object in
            // `people.js` when sending messages.
            return {
                email,
                full_name: email,
                unknown_local_echo_user: true,
            };
        }

        if (person.user_id === message.sender_id) {
            sender_in_display_recipients = true;
        }

        // NORMAL PATH
        //
        // This should match the format of display_recipient
        // objects generated by the backend code in display_recipient.py,
        // which is why we create a new object with a `.id` field
        // rather than a `.user_id` field.
        return {
            id: person.user_id,
            email: person.email,
            full_name: person.full_name,
        };
    });

    if (!sender_in_display_recipients) {
        // Ensure that the current user is included in
        // display_recipient for group direct messages.
        display_recipient.push({
            id: message.sender_id,
            email: message.sender_email,
            full_name: message.sender_full_name,
        });
    }
    return display_recipient;
}

export function insert_local_message(message_request, local_id_float, insert_new_messages) {
    // Shallow clone of message request object that is turned into something suitable
    // for zulip.js:add_message
    // Keep this in sync with changes to compose.create_message_object
    let message = {...message_request};

    message.raw_content = message.content;

    // NOTE: This will parse synchronously. We're not using the async pipeline
    message = {
        ...message,
        ...markdown.render(message.raw_content),
    };

    message.content_type = "text/html";
    message.sender_email = people.my_current_email();
    message.sender_full_name = people.my_full_name();
    message.avatar_url = current_user.avatar_url;
    message.timestamp = Date.now() / 1000;
    message.local_id = local_id_float.toString();
    message.locally_echoed = true;
    message.id = local_id_float;
    if (message.topic === undefined) {
        message.topic_links = [];
    } else {
        message.topic_links = markdown.get_topic_links(message.topic);
    }

    waiting_for_id.set(message.local_id, message);
    waiting_for_ack.set(message.local_id, message);

    message.display_recipient = build_display_recipient(message);

    insert_new_messages([message], true);

    return message;
}

export function is_slash_command(content) {
    return !content.startsWith("/me") && content.startsWith("/");
}

export function try_deliver_locally(message_request, insert_new_messages) {
    // Checks if the message request can be locally echoed, and if so,
    // adds a local echoed copy of the message to appropriate message lists.
    //
    // Returns the message object, or undefined if it cannot be
    // echoed; in that case, the compose box will remain in the
    // sending state rather than being cleared to allow composing a
    // next message.
    //
    // Notably, this algorithm will allow locally echoing a message in
    // cases where we are currently looking at a search view where
    // `!filter.can_apply_locally(message)`; so it is possible for a
    // message to be locally echoed but not appear in the current
    // view; this is useful to ensure it will be visible in other
    // views that we might navigate to before we get a response from
    // the server.
    if (markdown.contains_backend_only_syntax(message_request.content)) {
        return undefined;
    }

    if (is_slash_command(message_request.content)) {
        return undefined;
    }

    const local_id_float = local_message.get_next_id_float();

    if (!local_id_float) {
        // This can happen for legit reasons.
        return undefined;
    }

    // Now that we've committed to delivering the message locally, we
    // shrink the compose-box if it is in the full-screen state. This
    // would have happened anyway in clear_compose_box, however, we
    // need to this operation before inserting the local message into
    // the feed. Otherwise, the out-of-view notification will be
    // always triggered on the top of compose-box, regardless of
    // whether the message would be visible after shrinking compose,
    // because compose occludes the whole screen.
    if (compose_ui.is_full_size()) {
        compose_ui.make_compose_box_original_size();
    }

    const message = insert_local_message(message_request, local_id_float, insert_new_messages);
    return message;
}

export function edit_locally(message, request) {
    // Responsible for doing the rendering work of locally editing the
    // content of a message.  This is used in several code paths:
    // * Editing a message where a message was locally echoed but
    //   it got an error back from the server
    // * Locally echoing any content-only edits to fully sent messages
    // * Restoring the original content should the server return an
    //   error after having locally echoed content-only messages.
    // The details of what should be changed are encoded in the request.
    const raw_content = request.raw_content;
    const message_content_edited = raw_content !== undefined && message.raw_content !== raw_content;

    if (request.new_topic !== undefined || request.new_stream_id !== undefined) {
        const new_stream_id = request.new_stream_id;
        const new_topic = request.new_topic;
        stream_topic_history.remove_messages({
            stream_id: message.stream_id,
            topic_name: message.topic,
            num_messages: 1,
            max_removed_msg_id: message.id,
        });

        if (new_stream_id !== undefined) {
            message.stream_id = new_stream_id;
        }
        if (new_topic !== undefined) {
            message.topic = new_topic;
        }

        stream_topic_history.add_message({
            stream_id: message.stream_id,
            topic_name: message.topic,
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
            // Otherwise, we Markdown-render the message; this resets
            // all flags, so we need to restore those flags that are
            // properties of how the user has interacted with the
            // message, and not its rendering.
            const {content, flags, is_me_message} = markdown.render(message.raw_content);
            message.content = content;
            message.flags = flags;
            message.is_me_message = is_me_message;
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
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        msg_list.view.rerender_messages([message]);
    }
    stream_list.update_streams_sidebar();
    pm_list.update_private_messages();
    return message;
}

export function reify_message_id(local_id, server_id) {
    const message = waiting_for_id.get(local_id);
    waiting_for_id.delete(local_id);

    // reify_message_id is called both on receiving a self-sent message
    // from the server, and on receiving the response to the send request
    // Reification is only needed the first time the server id is found
    if (message === undefined) {
        return;
    }

    message.id = server_id;
    message.locally_echoed = false;

    const opts = {old_id: Number.parseFloat(local_id), new_id: server_id};

    message_store.reify_message_id(opts);
    update_message_lists(opts);
    compose_notifications.reify_message_id(opts);
    recent_view_data.reify_message_id_if_available(opts);
}

export function update_message_lists({old_id, new_id}) {
    if (all_messages_data !== undefined) {
        all_messages_data.change_message_id(old_id, new_id);
    }
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        msg_list.change_message_id(old_id, new_id);
        msg_list.view.change_message_id(old_id, new_id);
    }
}

export function process_from_server(messages) {
    const msgs_to_rerender = [];
    const non_echo_messages = [];

    for (const message of messages) {
        // In case we get the sent message before we get the send ACK, reify here

        const local_id = message.local_id;
        const client_message = waiting_for_ack.get(local_id);
        if (client_message === undefined) {
            // For messages that weren't locally echoed, we go through
            // the "main" codepath that doesn't have to id reconciliation.
            // We simply return non-echo messages to our caller.
            non_echo_messages.push(message);
            continue;
        }

        reify_message_id(local_id, message.id);

        if (message_store.get(message.id).failed_request) {
            failed_message_success(message.id);
        }

        if (client_message.content !== message.content) {
            client_message.content = message.content;
            sent_messages.mark_disparity(local_id);
        }
        sent_messages.report_event_received(local_id);

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

        client_message.topic_links = message.topic_links;
        client_message.is_me_message = message.is_me_message;
        client_message.submessages = message.submessages;

        msgs_to_rerender.push(client_message);
        waiting_for_ack.delete(local_id);
    }

    if (msgs_to_rerender.length > 0) {
        // In theory, we could just rerender messages where there were
        // changes in either the rounded timestamp we display or the
        // message content, but in practice, there's no harm to just
        // doing it unconditionally.
        for (const msg_list of message_lists.all_rendered_message_lists()) {
            msg_list.view.rerender_messages(msgs_to_rerender);
        }
    }

    return non_echo_messages;
}

export function _patch_waiting_for_ack(data) {
    // Only for testing
    waiting_for_ack = data;
}

export function message_send_error(message_id, error_response) {
    // Error sending message, show inline
    const message = message_store.get(message_id);
    message.failed_request = true;
    message.show_slow_send_spinner = false;

    show_message_failed(message_id, error_response);
}

function abort_message(message) {
    // Remove in all lists in which it exists
    all_messages_data.remove([message.id]);
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        msg_list.remove_and_rerender([message.id]);
    }
}

export function display_slow_send_loading_spinner(message) {
    const $rows = message_lists.all_rendered_row_for_message_id(message.id);
    if (message.locally_echoed && !message.failed_request) {
        message.show_slow_send_spinner = true;
        $rows.find(".slow-send-spinner").removeClass("hidden");
        // We don't need to do anything special to ensure this gets
        // cleaned up if the message is delivered, because the
        // message's HTML gets replaced once the message is
        // successfully sent.
    }
}

export function initialize({on_send_message_success, send_message}) {
    function on_failed_action(selector, callback) {
        $("#main_div").on("click", selector, function (e) {
            e.stopPropagation();
            const $row = $(this).closest(".message_row");
            const local_id = rows.local_echo_id($row);
            // Message should be waiting for ack and only have a local id,
            // otherwise send would not have failed
            const message = waiting_for_ack.get(local_id);
            if (message === undefined) {
                blueslip.warn(
                    "Got resend or retry on failure request but did not find message in ack list " +
                        local_id,
                );
                return;
            }
            callback(message, $row, {on_send_message_success, send_message});
        });
    }

    on_failed_action(".remove-failed-message", abort_message);
    on_failed_action(".refresh-failed-message", resend_message);
}
