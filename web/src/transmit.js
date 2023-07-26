import * as Sentry from "@sentry/browser";

import * as blueslip from "./blueslip";
import * as channel from "./channel";
import {page_params} from "./page_params";
import * as people from "./people";
import * as reload from "./reload";
import * as reload_state from "./reload_state";
import * as sent_messages from "./sent_messages";
import * as stream_data from "./stream_data";

export function send_message(request, on_success, error) {
    if (!request.resend) {
        sent_messages.start_tracking_message({
            local_id: request.local_id,
            locally_echoed: request.locally_echoed,
        });
    }
    const txn = sent_messages.start_send(request.local_id);
    try {
        const scope = Sentry.getCurrentHub().pushScope();
        scope.setSpan(txn);
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

                const response = channel.xhr_error_message("Error sending message", xhr);
                error(response);
            },
        });
    } finally {
        Sentry.getCurrentHub().popScope();
    }
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
        const stream_name = stream_data.get_stream_name_from_id(message.stream_id);

        const mention = people.get_mention_syntax(message.sender_full_name, message.sender_id);

        content = mention + " " + content;

        reply.type = "stream";
        reply.to = stream_name;
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

    blueslip.error("unknown message type", {message, content});
}
