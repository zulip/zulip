import * as blueslip from "./blueslip";
import * as channel from "./channel";
import * as compose_state from "./compose_state";
import {page_params} from "./page_params";
import * as people from "./people";
import * as reload from "./reload";
import * as reload_state from "./reload_state";
import * as sent_messages from "./sent_messages";
import * as unsent_messages from "./unsent_messages";

const max_unsent_msg_count = 4;
let current_unsent_msg_count = 0;

export function send_message(request, on_success, error) {
    // We need to store the message content here as - when a message
    // is echoed locally then it is removed from the compose box, but
    // if the message is not sent to the server (because of some possible
    // issues like server is down) then it will be lost during the server
    // reload. Hence, here we are storing that message content, in the
    // localStorage, when there is connection problem or server is unreachable.
    const saved_message_content = compose_state.message_content();
    channel.post({
        url: "/json/messages",
        data: request,
        success: function success(data) {
            // Call back to our callers to do things like closing the compose
            // box and turning off spinners and reifying locally echoed messages.
            on_success(data);

            // Once everything is done, get ready to report times to the server.
            sent_messages.report_server_ack(request.local_id);
        },
        error(xhr, error_type) {
            if (error_type !== "timeout" && reload_state.is_pending()) {
                // The error might be due to the server changing
                reload.initiate({
                    immediate: true,
                    save_pointer: true,
                    save_narrow: true,
                    save_compose: true,
                    send_after_reload: true,
                });
                return;
            }

            if (
                channel.is_server_unreachable(xhr) &&
                current_unsent_msg_count < max_unsent_msg_count
            ) {
                unsent_messages.store_unsent_message(saved_message_content);
                current_unsent_msg_count += 1;
                return;
            }

            const response = channel.xhr_error_message("Error sending message", xhr);
            error(response);
        },
    });
}

export function reply_message(opts) {
    // This code does an application-triggered reply to a message (as
    // opposed to the user themselves doing it).  Its only use case
    // for now is experimental widget-aware bots, so treat this as
    // somewhat beta code.  To understand the use case, think of a
    // bot that wants to give users 3 or 4 canned replies to some
    // choice, but it wants to front-end each of these options
    // with a one-click button.  This function is part of that architecture.
    const message = opts.message;
    let content = opts.content;

    function success() {
        // TODO: If server response comes back before the message event,
        //       we could show it earlier, although that creates some
        //       complexity.  For now do nothing.  (Note that send_message
        //       already handles things like reporting times to the server.)
    }

    function error() {
        // TODO: In our current use case, which is widgets, to meaningfully
        //       handle errors, we would want the widget to provide some
        //       kind of callback to us so it can do some appropriate UI.
        //       For now do nothing.
    }

    const locally_echoed = false;
    const local_id = sent_messages.get_new_local_id();

    const reply = {
        sender_id: page_params.user_id,
        queue_id: page_params.queue_id,
        local_id,
    };

    sent_messages.start_tracking_message({
        local_id,
        locally_echoed,
    });

    if (message.type === "stream") {
        const stream = message.stream;

        const mention = people.get_mention_syntax(message.sender_full_name, message.sender_id);

        content = mention + " " + content;

        reply.type = "stream";
        reply.to = stream;
        reply.content = content;
        reply.topic = message.topic;

        send_message(reply, success, error);
        return;
    }

    if (message.type === "private") {
        const pm_recipient = people.pm_reply_to(message);

        reply.type = "private";
        reply.to = JSON.stringify(pm_recipient.split(","));
        reply.content = content;

        send_message(reply, success, error);
        return;
    }

    blueslip.error("unknown message type: " + message.type);
}
