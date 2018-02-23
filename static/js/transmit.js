var transmit = (function () {

var exports = {};

var socket;
$(function () {
    // We initialize the socket inside a function so that this code
    // runs after `csrf_token` is initialized in setup.js.
    if (page_params.use_websockets) {
        socket = new Socket("/sockjs");
    }
    // For debugging.  The socket will eventually move out of this file anyway.
    exports._socket = socket;
});

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
            if (error_type !== 'timeout' && reload.is_pending()) {
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
    var message = opts.message;
    var content = opts.content;

    function success() {
        // TODO
    }

    function error() {
        // TODO
    }

    var locally_echoed = false;
    var local_id = sent_messages.get_new_local_id();

    // TODO: move to transmit.js
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

        var mention = '@**' + message.sender_full_name + '**';

        content = mention + ' ' + content;

        reply.type = 'stream';
        reply.to  = stream;
        reply.content = content;
        reply.subject = message.subject;

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
