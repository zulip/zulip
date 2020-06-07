const noop = function () {};

set_global('$', global.make_zjquery());
set_global('XDate', zrequire('XDate', 'xdate'));

zrequire('rows');
zrequire('message_copy');

const date_format = function (ts) {
    const time = new XDate(ts * 1000);
    const tz_offset = -time.getTimezoneOffset() / 60;
    return time.toLocaleDateString() + " " + time.toLocaleTimeString() +
    ' (UTC' + (tz_offset < 0 ? '' : '+') + tz_offset + ')';
};

const copy_selected_messages = message_copy.copy_selected_messages;
const push_message = message_copy.push_message;
const select_message = message_copy.select_message;
const select_until_message = message_copy.select_until_message;
const show_copied_alert = message_copy.show_copied_alert;
const clean_copied_messages = message_copy.clean_copied_messages;
const clipboard_error_handler = message_copy.clipboard_error_handler;
const clipboard_success_handler = message_copy.clipboard_success_handler;
const concat_markdown = message_copy.concat_markdown;
const messages = message_copy.messages;

const message_box_id = 85;
const raw_content_get =  date_format(1582394301) + ' @_**aaron**: first message';
const messages_list = [
    {
        id: 85,
    },
    {
        id: 86,
    },
    {
        id: 89,
    },
    {
        id: 90,
    },
];

function stub_channel_get(success_value) {
    set_global('channel', {
        get: function (opts) {
            opts.success(success_value);
        },
    });
}

set_global('rows', {
    id: function (row) {
        return row.id;
    },
});

set_global('i18n', {
    t: function (text) {
        return text;
    },
});

set_global('popovers', {
    hide_actions_popover: noop,
});

set_global('ClipboardJS', function (sel) {
    assert.equal(sel, '#btn_copy_message_markdown_' + message_box_id);
    this.on = function () {};
});

run_test('copy selected messages', () => {
    const message_row_1 = $('#zhome' + messages_list[0].id);
    message_row_1.id = messages_list[0].id;
    message_row_1.length = 1;
    const message_row_2 = $('#zhome' + messages_list[1].id);
    message_row_2.id = messages_list[1].id;
    message_row_2.length = 1;
    const message_row_3 = $('#zhome' + messages_list[2].id);
    message_row_3.id = messages_list[2].id;
    message_row_3.length = 1;
    const message_row_4 = $('#zhome' + messages_list[3].id);
    message_row_4.id = messages_list[3].id;
    message_row_4.length = 1;

    const selected_messages = $(".copy_selected_message");
    selected_messages.data = [message_row_1, message_row_2, message_row_3, message_row_4];
    selected_messages.eq = function (index) {
        return selected_messages.data[index];
    };
    message_copy.push_message = noop;
    message_copy.concat_markdown = function () {
        return raw_content_get;
    };
    stub_channel_get({
        messages: [],
    });
    copy_selected_messages(message_box_id);
    assert.equal($('#copy_message_markdown_' + message_box_id).val(), raw_content_get);

});

run_test('push a message', () => {
    const message_row_1 = $('#zhome' + messages_list[0].id);
    message_row_1.id = messages_list[0].id;
    const message_row_2 = $('#zhome' + messages_list[1].id);
    message_row_2.id = messages_list[1].id;
    push_message(message_row_1);
    push_message(message_row_2);
    assert.equal(messages[0], messages_list[0].id);
});

run_test('select a message', () => {
    const message_box = $('<div class="message_box">');
    const message_row = $('#zhome' + messages_list[0].id);
    message_box.closest = function () {
        return message_row;
    };

    // selecting a message
    select_message(message_box);
    assert.equal($('#zhome' + messages_list[0].id).hasClass("copy_selected_message"), true);
    // unselecting
    select_message(message_box);
    assert.equal($('#zhome' + messages_list[0].id).hasClass("copy_selected_message"), false);
});

run_test('select a message range and clean copied', () => {
    const message_row_1 = $('#zhome' + messages_list[0].id);
    message_row_1.id = messages_list[0].id;
    message_row_1.length = 1;
    const message_row_2 = $('#zhome' + messages_list[1].id);
    message_row_2.id = messages_list[1].id;
    message_row_2.length = 1;
    const message_row_3 = $('#zhome' + messages_list[2].id);
    message_row_3.id = messages_list[2].id;
    message_row_3.length = 1;
    const message_row_4 = $('#zhome' + messages_list[3].id);
    message_row_4.id = messages_list[3].id;
    message_row_4.length = 1;

    set_global('rows', {
        next_visible: function (row) {
            switch (row.id) {
            case messages_list[0].id:
                return message_row_2;
            case messages_list[1].id:
                return message_row_3;
            case messages_list[2].id:
                return message_row_4;
            case messages_list[3].id:
                return { length: 0 };
            }
        },
        id: function (row) {
            return row.id;
        },
    });

    // Selecting a range of messages
    select_until_message(message_row_1, message_row_4);

    assert.equal(message_row_1.hasClass("copy_selected_message"), true);
    assert.equal(message_row_2.hasClass("copy_selected_message"), true);
    assert.equal(message_row_3.hasClass("copy_selected_message"), true);
    assert.equal(message_row_4.hasClass("copy_selected_message"), true);


    const selected_messages = $(".copy_selected_message");
    selected_messages.data = [message_row_1, message_row_2, message_row_3, message_row_4];
    selected_messages.removeClass = function () {
        for (const msg of selected_messages.data) {
            msg.removeClass("copy_selected_message");
        }
    };

    // Cleaning the selected messages

    $('#messages_markdown_' + messages_list[0].id).show();
    assert($('#messages_markdown_' + messages_list[0].id).visible());
    $('#copy_message_markdown_' + messages_list[0].id).val(raw_content_get);
    clean_copied_messages(messages_list[0].id);

    assert.equal(message_row_1.hasClass("copy_selected_message"), false);
    assert.equal(message_row_2.hasClass("copy_selected_message"), false);
    assert.equal(message_row_3.hasClass("copy_selected_message"), false);
    assert.equal(message_row_4.hasClass("copy_selected_message"), false);

    assert(!$('#messages_markdown_' + messages_list[0].id).visible());
    assert.equal($('#copy_message_markdown_' + messages_list[0].id).val(), '');

    // When the first message is before the second one

    select_until_message(message_row_4, message_row_1);

    assert.equal(message_row_1.hasClass("copy_selected_message"), false);
    assert.equal(message_row_2.hasClass("copy_selected_message"), false);
    assert.equal(message_row_3.hasClass("copy_selected_message"), false);
    assert.equal(message_row_4.hasClass("copy_selected_message"), false);
});

run_test('show copied alert', () => {
    const alert_src = $('<span class="alert-msg pull-right"></span>');
    const alert = $(".selected_message[zid='" + messages_list[0].id + "']");
    alert.set_find_results('.alert-msg', alert_src);
    alert_src.delay = function () {
        return alert_src;
    };
    alert_src.fadeOut = function () {
        return alert_src;
    };

    show_copied_alert(messages_list[0].id);
    assert.equal(alert_src.text(), "Copied!");

    message_copy.show_copied_alert = noop;
    message_copy.clean_copied_messages = noop;
    const event = {
        trigger: $.create('trigger'),
    };
    event.trigger.attr('data-message', message_box_id);
    clipboard_success_handler(event);
    clipboard_error_handler(event);
});

run_test('concatenate markdown', () => {
    const messages = [
        {
            timestamp: 1582394301,
            sender_full_name: "Polonius",
            content: "Strange violin",
        },
        {
            timestamp: 1582520201,
            sender_full_name: "Aaron",
            content: "Basketball player",
        },
    ];
    const date_1 = date_format(messages[0].timestamp);
    const date_2 = date_format(messages[1].timestamp);

    const expected = date_1.concat(" @_**" + messages[0].sender_full_name + "**: \n\n")
        .concat(messages[0].content + "\n\n")
        .concat(date_2)
        .concat(" @_**" + messages[1].sender_full_name + "**: \n\n")
        .concat(messages[1].content + "\n\n");

    const markdown = concat_markdown(messages);
    assert.equal(markdown, expected);

});
