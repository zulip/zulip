var noop = function () {};

set_global('document', {});
set_global('window', {
    addEventListener: noop,
});
global.stub_out_jquery();

zrequire('message_store');
zrequire('server_events_dispatch');
zrequire('server_events');

set_global('blueslip', {});
set_global('channel', {});
set_global('home_msg_list', {
    select_id: noop,
    selected_id: function () {return 1;},
});
set_global('page_params', {test_suite: false});
set_global('reload', {
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

(function test_message_event() {
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
}());

(function test_pointer_event() {
    var event = {
        type: 'pointer',
        pointer: 999,
    };

    global.pointer.furthest_read = 0;
    global.pointer.server_furthest_read = 0;
    server_events._get_events_success([event]);
    assert.equal(global.pointer.furthest_read, event.pointer);
    assert.equal(global.pointer.server_furthest_read, event.pointer);
}());


// Start blueslip tests here

var setup = function (results) {
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
    global.blueslip.error = function (msg, more_info, stack) {
        results.msg = msg;
        results.more_info = more_info;
        results.stack = stack;
    };
    global.blueslip.exception_msg = function (ex) {
        return ex.message;
    };
};

(function test_event_dispatch_error() {
    var results = {};
    setup(results);

    var data = {events: [{type: 'stream', op: 'update', id: 1, other: 'thing'}]};
    global.channel.get = function (options) {
        options.success(data);
    };

    server_events.restart_get_events();

    assert.equal(results.msg, 'Failed to process an event\n' +
                              'subs update error');
    assert.equal(results.more_info.event.type , 'stream');
    assert.equal(results.more_info.event.op , 'update');
    assert.equal(results.more_info.event.id , 1);
    assert.equal(results.more_info.other , undefined);
}());


(function test_event_new_message_error() {
    var results = {};
    setup(results);

    var data = {events: [{type: 'message', id: 1, other: 'thing', message: {}}]};
    global.channel.get = function (options) {
        options.success(data);
    };

    server_events.restart_get_events();

    assert.equal(results.msg, 'Failed to insert new messages\n' +
                               'insert error');
    assert.equal(results.more_info, undefined);
}());

(function test_event_edit_message_error() {
    var results = {};
    setup(results);

    var data = {events: [{type: 'update_message', id: 1, other: 'thing'}]};
    global.channel.get = function (options) {
        options.success(data);
    };

    server_events.restart_get_events();

    assert.equal(results.msg, 'Failed to update messages\n' +
                              'update error');
    assert.equal(results.more_info, undefined);
}());
