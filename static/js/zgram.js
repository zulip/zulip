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

    message.timestamp = local_message.now();
    message.simulated = true;
    message.type = 'zgram';
    exports.process_row(message);
};

exports.display_zgram = function (msg) {
    $('#zgram-container').show();
    var html = templates.render('zgram-box', msg);
    $('#zgram-box-content').html(html);
};

exports.process = function (content) {
    // TEMPORARY CODE:
    //
    // We probably will eventually just have API clients
    // send zgrams, with no UI hooks.  But this is convenient
    // code for prototyping purposes.

    var prefix = '/yesno ';
    if (content.startsWith(prefix)) {
        var pill_user_ids = compose_pm_pill.get_user_ids();

        if (pill_user_ids.length !== 1) {
            blueslip.warn('/yesno requires a single PM user target');
            return false;
        }

        var question = content.slice(prefix.length);

        var extra_data = {
            type: 'choices',
            heading: question,
            choices: [
                {
                    short_name: 'Y',
                    long_name: 'yes',
                    reply: 'yes',
                },
                {
                    short_name: 'N',
                    long_name: 'no',
                    reply: 'no',
                },
            ],
        };

        var target_user_id = pill_user_ids[0];

        var data = {
            content: content,
            target_user_id: target_user_id,
            extra_data: extra_data,
            widget_type: 'zform',
        };
        exports.send({
            data: data,
        });
        return true;
    }

    return false;
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

exports.process_row = function (message) {
    message.small_avatar_url = people.small_avatar_url(message);
    message.sender_full_name = people.get_person_from_user_id(message.sender_id).full_name;

    if (!message) {
        return;
    }

    if (message.type !== 'zgram') {
        return;
    }

    exports.display_zgram(message);
    var content_holder = $('#zgram-widget');

    var widget_elem;
    if (message.widget) {
        // Use local to work around linter.  We can trust this
        // value because it comes from a template.
        exports.display_zgram(message);
        widget_elem = message.widget_elem;
        var content_holder = $('#zgram-widget');
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
