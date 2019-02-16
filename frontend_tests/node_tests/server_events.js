var noop = function () {};

set_global('document', {});
global.patch_builtin('window', {
    addEventListener: noop,
});
global.stub_out_jquery();

zrequire('message_store');
zrequire('server_events_dispatch');
zrequire('server_events');
zrequire('sent_messages');

set_global('blueslip', global.make_zblueslip());
set_global('channel', {});
set_global('home_msg_list', {
    select_id: noop,
    selected_id: function () {return 1;},
});
set_global('page_params', {test_suite: false});
set_global('reload_state', {
    is_in_progress: function () {return false;},
});

// we also directly write to pointer
set_global('pointer', {});

set_global('echo', {
    process_from_server: function (messages) {
        return messages;
    },
    set_realm_filters: noop,
});
set_global('ui_report', {
    hide_error: function () { return false; },
    show_error: function () { return false; },
});


server_events.home_view_loaded();

run_test('message_event', () => {
    var event = {
        type: 'message',
        message: {
            content: 'hello',
        },
        flags: [],
    };

    var inserted;
    set_global('message_events', {
        insert_new_messages: function (messages) {
            assert.equal(messages[0].content, event.message.content);
            inserted = true;
        },
    });

    server_events._get_events_success([event]);
    assert(inserted);
});

run_test('pointer_event', () => {
    var event = {
        type: 'pointer',
        pointer: 999,
    };

    global.pointer.furthest_read = 0;
    global.pointer.server_furthest_read = 0;
    server_events._get_events_success([event]);
    assert.equal(global.pointer.furthest_read, event.pointer);
    assert.equal(global.pointer.server_furthest_read, event.pointer);
});


// Start blueslip tests here

var setup = function () {
    server_events.home_view_loaded();
    set_global('message_events', {
        insert_new_messages: function () {
            throw Error('insert error');
        },
        update_messages: function () {
            throw Error('update error');
        },
    });
    set_global('stream_events', {
        update_property: function () {
            throw Error('subs update error');
        },
    });
};

run_test('event_dispatch_error', () => {
    setup();

    var data = {events: [{type: 'stream', op: 'update', id: 1, other: 'thing'}]};
    global.channel.get = function (options) {
        options.success(data);
    };

    blueslip.set_test_data('error', 'Failed to process an event\nsubs update error');

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs('error');
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info.event.type, 'stream');
    assert.equal(logs[0].more_info.event.op, 'update');
    assert.equal(logs[0].more_info.event.id, 1);
    assert.equal(logs[0].more_info.other, undefined);
    blueslip.clear_test_data();
});


run_test('event_new_message_error', () => {
    setup();

    var data = {events: [{type: 'message', id: 1, other: 'thing', message: {}}]};
    global.channel.get = function (options) {
        options.success(data);
    };

    blueslip.set_test_data('error', 'Failed to insert new messages\ninsert error');

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs('error');
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info, undefined);
    blueslip.clear_test_data();
});

run_test('event_edit_message_error', () => {
    setup();
    var data = {events: [{type: 'update_message', id: 1, other: 'thing'}]};
    global.channel.get = function (options) {
        options.success(data);
    };
    blueslip.set_test_data('error', 'Failed to update messages\nupdate error');

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs('error');
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info, undefined);
    blueslip.clear_test_data();
});
