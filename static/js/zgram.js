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

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = zgram;
}
