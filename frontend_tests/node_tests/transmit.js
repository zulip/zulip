var noop = function () {};

set_global('$', global.make_zjquery());
set_global('page_params', {
    use_websockets: true,
});

set_global('channel', {});
set_global('navigator', {});
set_global('reload', {});
set_global('reload_state', {});
set_global('socket', {});
set_global('Socket', function () {
    return global.socket;
});
set_global('sent_messages', {
    start_tracking_message: noop,
    report_server_ack: noop,
});
set_global('blueslip', global.make_zblueslip());

zrequire('people');
zrequire('util');
zrequire('transmit');

function test_with_mock_socket(test_params) {
    transmit.initialize();
    var socket_send_called;
    var send_args = {};

    global.socket.send = function (request, success, error) {
        global.socket.send = undefined;
        socket_send_called = true;

        // Save off args for check_send_args callback.
        send_args.request = request;
        send_args.success = success;
        send_args.error = error;
    };

    // Run the actual code here.
    test_params.run_code();

    assert(socket_send_called);
    test_params.check_send_args(send_args);
}

run_test('transmit_message_sockets', () => {
    page_params.use_websockets = true;
    global.navigator.userAgent = 'unittest_transmit_message';

    // Our request is mostly unimportant, except that the
    // socket_user_agent field will be added.
    var request = {foo: 'bar'};

    var success_func_checked = false;
    var success = function () {
        success_func_checked = true;
    };

    // Our error function gets wrapped, so we set up a real
    // function to test the wrapping mechanism.
    var error_func_checked = false;
    var error = function (error_msg) {
        assert.equal(error_msg, 'Error sending message: simulated_error');
        error_func_checked = true;
    };

    test_with_mock_socket({
        run_code: function () {
            transmit.send_message(request, success, error);
        },
        check_send_args: function (send_args) {
            // The real code patches new data on the request, rather
            // than making a copy, so we test both that it didn't
            // clone the object and that it did add a field.
            assert.equal(send_args.request, request);
            assert.deepEqual(send_args.request, {
                foo: 'bar',
                socket_user_agent: 'unittest_transmit_message',
            });

            send_args.success({});
            assert(success_func_checked);

            // Our error function does get wrapped, so we test by
            // using socket.send's error callback, which should
            // invoke our test error function via a wrapper
            // function in the real code.
            send_args.error('response', {msg: 'simulated_error'});
            assert(error_func_checked);
        },
    });
});

page_params.use_websockets = false;

run_test('transmit_message_ajax', () => {

    var success_func_called;
    var success = function () {
        success_func_called = true;
    };

    var request = {foo: 'bar'};

    channel.post = function (opts) {
        assert.equal(opts.url, '/json/messages');
        assert.equal(opts.data.foo, 'bar');
        opts.success();
    };

    transmit.send_message(request, success);

    assert(success_func_called);

    channel.xhr_error_message = function (msg) {
        assert.equal(msg, 'Error sending message');
        return msg;
    };

    channel.post = function (opts) {
        assert.equal(opts.url, '/json/messages');
        assert.equal(opts.data.foo, 'bar');
        var xhr = 'whatever';
        opts.error(xhr, 'timeout');
    };

    var error_func_called;
    var error = function (response) {
        assert.equal(response, 'Error sending message');
        error_func_called = true;
    };
    transmit.send_message(request, success, error);
    assert(error_func_called);
});

run_test('transmit_message_ajax_reload_pending', () => {
    var success = function () { throw 'unexpected success'; };

    reload_state.is_pending = function () {
        return true;
    };

    var reload_initiated;
    reload.initiate = function (opts) {
        reload_initiated = true;
        assert.deepEqual(opts, {
            immediate: true,
            save_pointer: true,
            save_narrow: true,
            save_compose: true,
            send_after_reload: true,
        });
    };

    var request = {foo: 'bar'};

    var error_func_called;
    var error = function (response) {
        assert.equal(response, 'Error sending message');
        error_func_called = true;
    };

    error_func_called = false;
    channel.post = function (opts) {
        assert.equal(opts.url, '/json/messages');
        assert.equal(opts.data.foo, 'bar');
        var xhr = 'whatever';
        opts.error(xhr, 'bad request');
    };
    transmit.send_message(request, success, error);
    assert(!error_func_called);
    assert(reload_initiated);
});

run_test('reply_message_stream', () => {
    const stream_message = {
        type: 'stream',
        stream: 'social',
        topic: 'lunch',
        sender_full_name: 'Alice',
        sender_id: 123,
    };

    const content = 'hello';

    var send_message_args;

    transmit.send_message = (args) => {
        send_message_args = args;
    };

    page_params.user_id = 44;
    page_params.queue_id = 66;
    sent_messages.get_new_local_id = () => 99;

    transmit.reply_message({
        message: stream_message,
        content: content,
    });

    assert.deepEqual(send_message_args, {
        sender_id: 44,
        queue_id: 66,
        local_id: 99,
        type: 'stream',
        to: 'social',
        content: '@**Alice** hello',
        topic: 'lunch',
    });
});

run_test('reply_message_private', () => {
    const fred = {
        user_id: 3,
        email: 'fred@example.com',
        full_name: 'Fred Frost',
    };
    people.add(fred);

    people.is_my_user_id = () => false;

    const pm_message = {
        type: 'private',
        display_recipient: [
            {user_id: fred.user_id},
        ],
    };

    const content = 'hello';

    var send_message_args;

    transmit.send_message = (args) => {
        send_message_args = args;
    };

    page_params.user_id = 155;
    page_params.queue_id = 177;
    sent_messages.get_new_local_id = () => 199;

    transmit.reply_message({
        message: pm_message,
        content: content,
    });

    assert.deepEqual(send_message_args, {
        sender_id: 155,
        queue_id: 177,
        local_id: 199,
        type: 'private',
        to: '["fred@example.com"]',
        content: 'hello',
    });
});

run_test('reply_message_errors', () => {
    const bogus_message = {
        type: 'bogus',
    };

    blueslip.set_test_data('error', 'unknown message type: bogus');

    transmit.reply_message({
        message: bogus_message,
    });

    blueslip.clear_test_data();
});
