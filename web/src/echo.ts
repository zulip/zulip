import $ from "jquery";
import assert from "minimalistic-assert";
import {z} from "zod";

import * as alert_words from "./alert_words";
import * as blueslip from "./blueslip";
import * as compose_notifications from "./compose_notifications";
import * as compose_ui from "./compose_ui";
import * as echo_state from "./echo_state";
import * as local_message from "./local_message";
import * as markdown from "./markdown";
import * as message_events_util from "./message_events_util";
import * as message_lists from "./message_lists";
import * as message_live_update from "./message_live_update";
import * as message_store from "./message_store";
import type {DisplayRecipientUser, Message, RawMessage} from "./message_store";
import * as message_util from "./message_util";
import * as people from "./people";
import * as pm_list from "./pm_list";
import * as recent_view_data from "./recent_view_data";
import * as rows from "./rows";
import * as sent_messages from "./sent_messages";
import {current_user} from "./state_data";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as stream_topic_history from "./stream_topic_history";
import type {TopicLink} from "./types";
import * as util from "./util";

// Docs: https://zulip.readthedocs.io/en/latest/subsystems/sending-messages.html

type ServerMessage = RawMessage & {local_id?: string};

const send_message_api_response_schema = z.object({
    id: z.number(),
    automatic_new_visibility_policy: z.number().optional(),
});

type MessageRequestObject = {
    sender_id: number;
    queue_id: null | string;
    topic: string;
    content: string;
    to: string;
    draft_id: string | undefined;
};

type PrivateMessageObject = {
    type: "private";
    reply_to: string;
    private_message_recipient: string;
    to_user_ids: string | undefined;
};

type StreamMessageObject = {
    type: "stream";
    stream_id: number;
};

type MessageRequest = MessageRequestObject & (PrivateMessageObject | StreamMessageObject);

type LocalEditRequest = Partial<{
    raw_content: string | undefined;
    content: string;
    orig_content: string;
    orig_raw_content: string | undefined;
    new_topic: string;
    new_stream_id: number;
    starred: boolean;
    historical: boolean;
    collapsed: boolean;
    alerted: boolean;
    mentioned: boolean;
    mentioned_me_directly: boolean;
}>;

type LocalMessage = MessageRequestObject & {
    raw_content: string;
    flags: string[];
    is_me_message: boolean;
    content_type: string;
    sender_email: string;
    sender_full_name: string;
    avatar_url?: string | null | undefined;
    timestamp: number;
    local_id: string;
    locally_echoed: boolean;
    resend: boolean;
    id: number;
    topic_links: TopicLink[];
} & (
        | (StreamMessageObject & {display_recipient?: string})
        | (PrivateMessageObject & {display_recipient?: DisplayRecipientUser[]})
    );

type PostMessageAPIData = z.output<typeof send_message_api_response_schema>;

// These retry spinner functions return true if and only if the
// spinner already is in the requested state, which can be used to
// avoid sending duplicate requests.
function show_retry_spinner($row: JQuery): boolean {
    const $retry_spinner = $row.find(".refresh-failed-message");

    if (!$retry_spinner.hasClass("rotating")) {
        $retry_spinner.toggleClass("rotating", true);
        return false;
    }
    return true;
}

function hide_retry_spinner($row: JQuery): boolean {
    const $retry_spinner = $row.find(".refresh-failed-message");

    if ($retry_spinner.hasClass("rotating")) {
        $retry_spinner.toggleClass("rotating", false);
        return false;
    }
    return true;
}

function show_message_failed(message_id: number, failed_msg: string): void {
    // Failed to send message, so display inline retry/cancel
    message_live_update.update_message_in_all_views(message_id, ($row) => {
        $row.find(".slow-send-spinner").addClass("hidden");
        const $failed_div = $row.find(".message_failed");
        $failed_div.toggleClass("hide", false);
        $failed_div.find(".failed_text").attr("title", failed_msg);
    });
}

function show_failed_message_success(message_id: number): void {
    // Previously failed message succeeded
    message_live_update.update_message_in_all_views(message_id, ($row) => {
        $row.find(".message_failed").toggleClass("hide", true);
    });
}

function failed_message_success(message_id: number): void {
    message_store.get(message_id)!.failed_request = false;
    show_failed_message_success(message_id);
}

function resend_message(
    message: Message,
    $row: JQuery,
    {
        on_send_message_success,
        send_message,
    }: {
        on_send_message_success: (request: Message, data: PostMessageAPIData) => void;
        send_message: (
            request: Message,
            on_success: (raw_data: unknown) => void,
            error: (response: string, _server_error_code: string) => void,
        ) => void;
    },
): void {
    message.content = message.raw_content!;
    if (show_retry_spinner($row)) {
        // retry already in in progress
        return;
    }

    message.resend = true;

    function on_success(raw_data: unknown): void {
        const data = send_message_api_response_schema.parse(raw_data);
        const message_id = data.id;
        message.locally_echoed = true;

        hide_retry_spinner($row);

        on_send_message_success(message, data);

        // Resend succeeded, so mark as no longer failed
        failed_message_success(message_id);
    }

    function on_error(response: string, _server_error_code: string): void {
        message_send_error(message.id, response);
        setTimeout(() => {
            hide_retry_spinner($row);
        }, 300);
        blueslip.log("Manual resend of message failed");
    }

    send_message(message, on_success, on_error);
}

export function build_display_recipient(message: LocalMessage): DisplayRecipientUser[] | string {
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
        assert(person !== undefined);

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

export function insert_local_message(
    message_request: MessageRequest,
    local_id_float: number,
    insert_new_messages: (
        messages: LocalMessage[],
        send_by_this_client: boolean,
        deliver_locally: boolean,
    ) => Message[],
): Message {
    // Shallow clone of message request object that is turned into something suitable
    // for zulip.js:add_message
    // Keep this in sync with changes to compose.create_message_object
    const raw_content = message_request.content;
    const topic = message_request.topic;

    const local_message: LocalMessage = {
        ...message_request,
        ...markdown.render(raw_content),
        raw_content,
        content_type: "text/html",
        sender_email: people.my_current_email(),
        sender_full_name: people.my_full_name(),
        avatar_url: current_user.avatar_url,
        timestamp: Date.now() / 1000,
        local_id: local_id_float.toString(),
        locally_echoed: true,
        id: local_id_float,
        resend: false,
        is_me_message: false,
        topic_links: topic ? markdown.get_topic_links(topic) : [],
    };

    local_message.display_recipient = build_display_recipient(local_message);

    const [message] = insert_new_messages([local_message], true, true);
    assert(message !== undefined);
    assert(message.local_id !== undefined);
    echo_state.set_message_waiting_for_id(message.local_id, message);
    echo_state.set_message_waiting_for_ack(message.local_id, message);

    return message;
}

export function is_slash_command(content: string): boolean {
    return !content.startsWith("/me") && content.startsWith("/");
}

export function try_deliver_locally(
    message_request: MessageRequest,
    insert_new_messages: (
        messages: LocalMessage[],
        send_by_this_client: boolean,
        deliver_locally: boolean,
    ) => Message[],
): Message | undefined {
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
    if (
        message_request.type === "private" &&
        message_request.to_user_ids &&
        !people.user_can_initiate_direct_message_thread(message_request.to_user_ids) &&
        !message_util.get_direct_message_permission_hints(message_request.to_user_ids)
            .is_local_echo_safe
    ) {
        return undefined;
    }
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
    // shrink the compose-box if it is in an expanded state. This
    // would have happened anyway in clear_compose_box, however, we
    // need to this operation before inserting the local message into
    // the feed. Otherwise, the out-of-view notification will be
    // always triggered on the top of compose-box, regardless of
    // whether the message would be visible after shrinking compose,
    // because compose occludes the whole screen in full size state.
    if (compose_ui.is_expanded()) {
        compose_ui.make_compose_box_original_size();
    }

    const message = insert_local_message(message_request, local_id_float, insert_new_messages);
    return message;
}

export function edit_locally(message: Message, request: LocalEditRequest): Message {
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
        assert(message.type === "stream");
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
            message.mentioned = request.mentioned ?? false;
            message.mentioned_me_directly = request.mentioned_me_directly ?? false;
            message.alerted = request.alerted ?? false;
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

export function reify_message_id(local_id: string, server_id: number): void {
    const message = echo_state.get_message_waiting_for_id(local_id);
    echo_state.remove_message_from_waiting_for_id(local_id);

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

export function update_message_lists({old_id, new_id}: {old_id: number; new_id: number}): void {
    // Update the rendered data first since it is most user visible.
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        msg_list.change_message_id(old_id, new_id);
        msg_list.view.change_message_id(old_id, new_id);
    }

    for (const msg_list_data of message_lists.non_rendered_data()) {
        msg_list_data.change_message_id(old_id, new_id);
    }
}

export function process_from_server(messages: ServerMessage[]): ServerMessage[] {
    const msgs_to_rerender_or_add_to_narrow = [];
    // For messages that weren't locally echoed, we go through the
    // "main" codepath that doesn't have to id reconciliation.  We
    // simply return non-echo messages to our caller.
    const non_echo_messages = [];

    for (const message of messages) {
        // In case we get the sent message before we get the send ACK, reify here

        const local_id = message.local_id;

        if (local_id === undefined) {
            // The server only returns local_id to the client whose
            // queue_id was in the message send request, aka the
            // client that sent it. Messages sent by another client,
            // or where we didn't pass a local ID to the server,
            // cannot have been locally echoed.
            non_echo_messages.push(message);
            continue;
        }

        const client_message = echo_state.get_message_waiting_for_ack(local_id);
        if (client_message === undefined) {
            non_echo_messages.push(message);
            continue;
        }

        reify_message_id(local_id, message.id);

        if (message_store.get(message.id)?.failed_request) {
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

        client_message.topic_links = message.topic_links ?? [];
        client_message.is_me_message = message.is_me_message;
        client_message.submessages = message.submessages;

        msgs_to_rerender_or_add_to_narrow.push(client_message);
        echo_state.remove_message_from_waiting_for_ack(local_id);
    }

    if (msgs_to_rerender_or_add_to_narrow.length > 0) {
        for (const msg_list of message_lists.all_rendered_message_lists()) {
            if (!msg_list.data.filter.can_apply_locally()) {
                // If this message list is a search filter that we
                // cannot apply locally, we will not have locally
                // echoed echoed the message at all originally, and
                // must the server now whether to add it to the view.
                message_events_util.maybe_add_narrowed_messages(
                    msgs_to_rerender_or_add_to_narrow,
                    msg_list,
                    message_util.add_new_messages,
                );
            } else {
                // In theory, we could just rerender messages where there were
                // changes in either the rounded timestamp we display or the
                // message content, but in practice, there's no harm to just
                // doing it unconditionally.
                msg_list.view.rerender_messages(msgs_to_rerender_or_add_to_narrow);
            }
        }
    }

    return non_echo_messages;
}

export function message_send_error(message_id: number, error_response: string): void {
    // Error sending message, show inline
    const message = message_store.get(message_id)!;
    message.failed_request = true;
    message.show_slow_send_spinner = false;

    show_message_failed(message_id, error_response);
}

function abort_message(message: Message): void {
    // Update the rendered data first since it is most user visible.
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        msg_list.remove_and_rerender([message.id]);
    }

    for (const msg_list_data of message_lists.non_rendered_data()) {
        msg_list_data.remove([message.id]);
    }
}

export function display_slow_send_loading_spinner(message: Message): void {
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

export function initialize({
    on_send_message_success,
    send_message,
}: {
    on_send_message_success: (request: Message, data: PostMessageAPIData) => void;
    send_message: (
        request: Message,
        on_success: (raw_data: unknown) => void,
        error: (response: string, _server_error_code: string) => void,
    ) => void;
}): void {
    function on_failed_action(
        selector: string,
        callback: (
            message: Message,
            $row: JQuery,
            {
                on_send_message_success,
                send_message,
            }: {
                on_send_message_success: (request: Message, data: PostMessageAPIData) => void;
                send_message: (
                    request: Message,
                    on_success: (raw_data: unknown) => void,
                    error: (response: string, _server_error_code: string) => void,
                ) => void;
            },
        ) => void,
    ): void {
        $("#main_div").on("click", selector, function (this: HTMLElement, e) {
            e.stopPropagation();
            const $row = $(this).closest(".message_row");
            const local_id = rows.local_echo_id($row);
            // Message should be waiting for ack and only have a local id,
            // otherwise send would not have failed
            const message = echo_state.get_message_waiting_for_ack(local_id);
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
