zrequire('typing_status');

function return_false() { return false; }
function return_true() { return true; }
function return_alice() { return "alice"; }
function return_bob() { return "bob"; }

function make_time(secs) {
    // make times semi-realistic
    return 1000000 + 1000 * secs;
}

function returns_time(secs) {
    return function () { return make_time(secs); };
}

(function test_basics() {

    // invalid conversation basically does nothing
    var worker = {
        get_recipient: return_alice,
        is_valid_conversation: return_false,
    };
    typing_status.handle_text_input(worker);

    // Start setting up more testing state.
    typing_status.initialize_state();

    var events = {};

    function set_timeout(f, delay) {
        assert.equal(delay, 5000);
        events.idle_callback = f;
        return 'idle_timer_stub';
    }

    function clear_timeout() {
        events.timer_cleared = true;
    }

    global.patch_builtin('setTimeout', set_timeout);
    global.patch_builtin('clearTimeout', clear_timeout);

    function notify_server_start(recipient) {
        assert.equal(recipient, "alice");
        events.started = true;
    }

    function notify_server_stop(recipient) {
        assert.equal(recipient, "alice");
        events.stopped = true;
    }

    function clear_events() {
        events.idle_callback = undefined;
        events.started = false;
        events.stopped = false;
        events.timer_cleared = false;
    }

    function call_handler() {
        clear_events();
        typing_status.handle_text_input(worker);
    }

    function call_stop() {
        clear_events();
        typing_status.stop(worker);
    }

    worker = {
        get_recipient: return_alice,
        is_valid_conversation: return_true,
        get_current_time: returns_time(5),
        notify_server_start: notify_server_start,
        notify_server_stop: notify_server_stop,
    };

    // Start talking to alice.
    call_handler();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(5 + 10),
        idle_timer: 'idle_timer_stub',
        current_recipient: 'alice',
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert(events.idle_callback);

    // type again 3 seconds later
    worker.get_current_time = returns_time(8);
    call_handler();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(5 + 10),
        idle_timer: 'idle_timer_stub',
        current_recipient: 'alice',
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: false,
        stopped: false,
        timer_cleared: true,
    });
    assert(events.idle_callback);

    // type after 15 secs, so that we can notify the server
    // again
    worker.get_current_time = returns_time(18);
    call_handler();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(18 + 10),
        idle_timer: 'idle_timer_stub',
        current_recipient: 'alice',
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: true,
    });

    // Now call alice's idle callback that we captured earlier.
    var callback = events.idle_callback;
    clear_events();
    callback();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: undefined,
        idle_timer: undefined,
        current_recipient: undefined,
    });
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: true,
        timer_cleared: true,
    });

    // Call stop with nothing going on.
    call_stop();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: undefined,
        idle_timer: undefined,
        current_recipient: undefined,
    });
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: false,
        timer_cleared: false,
    });

    // Start talking to alice again.
    worker.get_current_time = returns_time(50);
    call_handler();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(50 + 10),
        idle_timer: 'idle_timer_stub',
        current_recipient: 'alice',
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert(events.idle_callback);

    // Explicitly stop alice.
    call_stop();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: undefined,
        idle_timer: undefined,
        current_recipient: undefined,
    });
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: true,
        timer_cleared: true,
    });

    // Start talking to alice again.
    worker.get_current_time = returns_time(80);
    call_handler();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(80 + 10),
        idle_timer: 'idle_timer_stub',
        current_recipient: 'alice',
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert(events.idle_callback);

    // Switch to an invalid conversation.
    worker.get_recipient = function () {
        return 'not-alice';
    };
    worker.is_valid_conversation = return_false;
    call_handler();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: undefined,
        idle_timer: undefined,
        current_recipient: undefined,
    });
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: true,
        timer_cleared: true,
    });

    // Switch to another invalid conversation.
    worker.get_recipient = function () {
        return 'another-bogus-one';
    };
    worker.is_valid_conversation = return_false;
    call_handler();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: undefined,
        idle_timer: undefined,
        current_recipient: undefined,
    });
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: false,
        timer_cleared: false,
    });

    // Start talking to alice again.
    worker.get_recipient = return_alice;
    worker.is_valid_conversation = return_true;
    worker.get_current_time = returns_time(170);
    call_handler();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(170 + 10),
        idle_timer: 'idle_timer_stub',
        current_recipient: 'alice',
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert(events.idle_callback);

    // Switch to bob now.
    worker.get_recipient = return_bob;
    worker.is_valid_conversation = return_true;
    worker.get_current_time = returns_time(171);

    worker.notify_server_start = function (recipient) {
        assert.equal(recipient, "bob");
        events.started = true;
    };

    call_handler();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(171 + 10),
        idle_timer: 'idle_timer_stub',
        current_recipient: 'bob',
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: true,
        timer_cleared: true,
    });
    assert(events.idle_callback);

}());
