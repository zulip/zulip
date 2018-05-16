var zgram = (function () {

var exports = {};

exports.test = function () {

    var message_id = local_message.get_next_id();
    var timestamp = local_message.now();

    var extra_data = {
        type: 'choices',
        heading: 'Choose a snack:',
        choices: [
            {
                type: 'multiple_choice',
                shortcut: 'A',
                answer: 'apple',
                reply: 'I would like an apple!',
            },
            {
                type: 'multiple_choice',
                shortcut: 'B',
                answer: 'biscuit',
                reply: 'A biscuit sounds appetizing.',
            },
        ],
    };

    var message = {
        zgram: true,
        sender_id: people.my_current_user_id(),
        id: message_id,
        display_recipient: 'FRED',
        content: 'test zgram',
        timestamp: timestamp,
        widget_type: 'form_letter',
        extra_data: extra_data,
    };

    local_message.insert_message(message);
};

exports.process_row = function (in_opts) {
    var row = in_opts.row;

    var message_id = in_opts.message_id;
    var message = message_store.get(message_id);

    if (!message) {
        return;
    }

    if (!message.zgram) {
        return;
    }

    var content_holder = row.find('.message_content');

    if (message.widget) {
        content_holder.html(message.widget_elem);
        return;
    }

    var widget_type = message.widget_type;
    var extra_data = message.extra_data;

    if (widget_type !== 'form_letter') {
        // Right now form_letter is our only widget that works with
        // zgrams.  More complicated widgets like tictactoe and
        // surveys need "real" Zulip messages under the current
        // architecture.
        return;
    }

    var elem = $('<div>');
    content_holder.html(elem);

    form_letter.activate({
        elem: row,
        extra_data: extra_data,
    });

    // This is hacky, we should just maintain our own list.
    message.widget_elem = elem;

};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = zgram;
}
