var assert = require('assert');

add_dependencies({
    util: 'js/util.js',
    tutorial: 'js/tutorial.js'
});

var noop = function () {};

set_global('document', {});
set_global('window', {
    addEventListener: noop
});
set_global('$', function () {
    return {
        hide: noop,
        trigger: noop
    };
});
global.$.now = noop;

// Prevent the get_events loop and watchdog from running
patch_builtin('setTimeout', noop);
patch_builtin('setInterval', noop);

set_global('blueslip', {});
set_global('channel', {});
set_global('home_msg_list', {
    selected_id: function () {return 1;}
});
set_global('page_params', {test_suite: false});


var server_events = require('js/server_events.js');

var setup = function (results) {
    server_events.home_view_loaded();
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
    global.channel.post = function (options) {
        options.success(data);
    };

    server_events.restart_get_events();

    assert.equal(results.msg, 'Failed to process an event\n' +
                              'subs is not defined');
    assert.equal(results.more_info.event.type , 'stream');
    assert.equal(results.more_info.event.op , 'update');
    assert.equal(results.more_info.event.id , 1);
    assert.equal(results.more_info.other , undefined);
}());


(function test_event_new_message_error() {
    var results = {};
    setup(results);

    var data = {events: [{type: 'message', id: 1, other: 'thing', message: {}}]};
    global.channel.post = function (options) {
        options.success(data);
    };

    server_events.restart_get_events();

    assert.equal(results.msg, 'Failed to insert new messages\n' +
                               'echo is not defined');
    assert.equal(results.more_info, undefined);
}());

(function test_event_edit_message_error() {
    var results = {};
    setup(results);

    var data = {events: [{type: 'update_message', id: 1, other: 'thing'}]};
    global.channel.post = function (options) {
        options.success(data);
    };

    server_events.restart_get_events();

    assert.equal(results.msg, 'Failed to update messages\n' +
                              'message_store is not defined');
    assert.equal(results.more_info, undefined);
}());
