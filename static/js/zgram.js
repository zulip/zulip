var zgram = (function () {

var exports = {};

exports._fake_send = function (message) {
    /*
        In early versions we are only building out the
        client side of zgrams, but they will eventually
        have a server-side component.  For now we
        simulate the "round trip" by immediately calling
        local_message.insert_message().
    */
    message.id = local_message.get_next_id();
    message.timestamp = local_message.now();
    message.simulated = true;
    message.sender_id = exports._fake_sender_id();
    message.type = 'zgram';
    local_message.insert_message(message);
};

exports.send = function (opts) {
    var data = opts.data;

    channel.post({
        url: '/json/zgram',
        data: {
            data: JSON.stringify(data),
        },
    });
};

exports.handle_event = function (event) {
    var message = event.data;

    message.id = local_message.get_next_id();
    message.timestamp = local_message.now();
    message.simulated = true;
    message.type = 'zgram';
    local_message.insert_message(message);
};

exports.simulate_simple_message = function () {
    var message = {
        type: 'zgram',
        display_recipient: people.my_full_name(),
        content: 'this is a simulated zgram (proof of concept)',
    };

    exports._fake_send(message);
};

exports._fake_sender_id = function () {
    var person = people.get_by_email('zoe@zulip.com');

    if (!person) {
        blueslip.error('The demo only works in a realm with zoe.');
        return;
    }

    return person.user_id;
};

exports.process_row = function (in_opts) {
    var row = in_opts.row;

    var message_id = in_opts.message_id;
    var message = message_store.get(message_id);

    if (!message) {
        return;
    }

    if (message.type !== 'zgram') {
        return;
    }

    var content_holder = row.find('.message_content');

    var widget_elem;
    if (message.widget) {
        // Use local to work around linter.  We can trust this
        // value because it comes from a template.
        widget_elem = message.widget_elem;
        content_holder.html(widget_elem);
        return;
    }

    var widget_type = message.widget_type;
    var extra_data = message.extra_data;

    if (widget_type !== 'zform') {
        // Right now zform is our only widget that works with
        // zgrams.  More complicated widgets like tictactoe and
        // surveys need "real" Zulip messages under the current
        // architecture.
        return;
    }

    widget_elem = $('<div>');
    content_holder.html(widget_elem);

    zform.activate({
        elem: widget_elem,
        message: message,
        extra_data: extra_data,
    });

    message.widget_elem = widget_elem;
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = zgram;
}
