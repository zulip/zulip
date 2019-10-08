zrequire('submessage');

set_global('channel', {});
set_global('widgetize', {});
set_global('message_store', {});

run_test('get_message_events', () => {
    var msg = {};

    assert.equal(submessage.get_message_events(msg), undefined);

    msg = {
        submessages: [],
    };
    assert.equal(submessage.get_message_events(msg), undefined);

    var submessages = [
        {id: 222, sender_id: 99, content: '84'},
        {id: 9, sender_id: 33, content: '42'},
    ];

    msg = {
        locally_echoed: true,
        submessages: submessages,
    };
    assert.equal(submessage.get_message_events(msg), undefined);

    msg = {
        submessages: submessages,
    };
    assert.deepEqual(submessage.get_message_events(msg), [
        {sender_id: 33, data: 42},
        {sender_id: 99, data: 84},
    ]);
});

run_test('make_server_callback', () => {
    var message_id = 444;
    var callback = submessage.make_server_callback(message_id);
    var was_posted;

    channel.post = function (opts) {
        was_posted = true;
        assert.deepEqual(opts, {
            url: '/json/submessage',
            data: {
                message_id: message_id,
                msg_type: 'whatever',
                content: '{"foo":32}',
            },
        });
    };

    callback({
        msg_type: 'whatever',
        data: {foo: 32},
    });

    assert(was_posted);
});

run_test('handle_event', () => {
    const message = {
        id: 42,
    };

    const event = {
        id: 11,
        msg_type: 'widget',
        sender_id: 99,
        message_id: message.id,
        content: '"some_data"',
    };

    var args;
    widgetize.handle_event = (opts) => {
        args = opts;
    };

    message_store.get = (msg_id) => {
        assert.equal(msg_id, message.id);
        return message;
    };

    submessage.handle_event(event);

    assert.deepEqual(args, {
        sender_id: 99,
        message_id: 42,
        data: 'some_data',
    });

    assert.deepEqual(message.submessages[0], event);
});
