var transmit = (function () {

var exports = {};

var socket;
exports.initialize =  function () {
    // We initialize the socket inside a function so that this code
    // runs after `csrf_token` is initialized in setup.js.
    if (page_params.use_websockets) {
        socket = new Socket("/sockjs");
    }
    // For debugging.  The socket will eventually move out of this file anyway.
    exports._socket = socket;
};

function send_message_socket(request, success, error) {
    request.socket_user_agent = navigator.userAgent;
    socket.send(request, success, function (type, resp) {
        var err_msg = "Error sending message";
        if (type === 'response') {
            err_msg += ": " + resp.msg;
        }
        error(err_msg);
    });
}

function send_message_ajax(request, success, error) {
    channel.post({
        url: '/json/messages',
        data: request,
        success: success,
        error: function (xhr, error_type) {
            if (error_type !== 'timeout' && reload_state.is_pending()) {
                // The error might be due to the server changing
                reload.initiate({immediate: true,
                                 save_pointer: true,
                                 save_narrow: true,
                                 save_compose: true,
                                 send_after_reload: true});
                return;
            }

            var response = channel.xhr_error_message("Error sending message", xhr);
            error(response);
        },
    });
}

exports.send_message = function (request, on_success, error) {
    function success(data) {
        // Call back to our callers to do things like closing the compose
        // box and turning off spinners and reifying locally echoed messages.
        on_success(data);

        // Once everything is done, get ready to report times to the server.
        sent_messages.report_server_ack(request.local_id);
    }

    if (page_params.use_websockets) {
        send_message_socket(request, success, error);
    } else {
        send_message_ajax(request, success, error);
    }
};

exports.reply_message = function (opts) {
    // This code does an application-triggered reply to a message (as
    // opposed to the user themselves doing it).  Its only use case
    // for now is experimental widget-aware bots, so treat this as
    // somewhat beta code.  To understand the use case, think of a
    // bot that wants to give users 3 or 4 canned replies to some
    // choice, but it wants to front-end each of these options
    // with a one-click button.  This function is part of that architecture.
    var message = opts.message;
    var content = opts.content;

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

    var locally_echoed = false;
    var local_id = sent_messages.get_new_local_id();

    var reply = {
        sender_id: page_params.user_id,
        queue_id: page_params.queue_id,
        local_id: local_id,
    };

    sent_messages.start_tracking_message({
        local_id: local_id,
        locally_echoed: locally_echoed,
    });

    if (message.type === 'stream') {
        var stream = message.stream;

        var mention = people.get_mention_syntax(message.sender_full_name, message.sender_id);

        content = mention + ' ' + content;

        reply.type = 'stream';
        reply.to  = stream;
        reply.content = content;
        util.set_message_topic(reply, util.get_message_topic(message));

        transmit.send_message(reply, success, error);
        return;
    }

    if (message.type === 'private') {
        var pm_recipient = people.pm_reply_to(message);

        reply.type = 'private';
        reply.to = JSON.stringify(pm_recipient.split(','));
        reply.content = content;

        transmit.send_message(reply, success, error);
        return;
    }

    blueslip.error('unknown message type: ' + message.type);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = transmit;
}
window.transmit = transmit;
