"use strict";

zrequire("typing");
zrequire("people");
zrequire("compose_pm_pill");
const typing_status = zrequire("typing_status", "shared/js/typing_status");

function make_time(secs) {
    // make times semi-realistic
    return 1000000 + 1000 * secs;
}

function returns_time(secs) {
    return function () {
        return make_time(secs);
    };
}

run_test("basics", () => {
    // invalid conversation basically does nothing
    let worker = {};
    typing_status.update(worker, null);

    // Start setting up more testing state.
    typing_status.initialize_state();

    const events = {};

    function set_timeout(f, delay) {
        assert.equal(delay, 5000);
        events.idle_callback = f;
        return "idle_timer_stub";
    }

    function clear_timeout() {
        events.timer_cleared = true;
    }

    global.patch_builtin("setTimeout", set_timeout);
    global.patch_builtin("clearTimeout", clear_timeout);

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

    function call_handler(new_recipient) {
        clear_events();
        typing_status.update(worker, new_recipient);
    }

    worker = {
        get_current_time: returns_time(5),
        notify_server_start,
        notify_server_stop,
    };

    // Start talking to alice.
    call_handler("alice");
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(5 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: "alice",
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
    call_handler("alice");
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(5 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: "alice",
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
    call_handler("alice");
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(18 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: "alice",
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: true,
    });

    // Now call alice's idle callback that we captured earlier.
    const callback = events.idle_callback;
    clear_events();
    callback();
    assert.deepEqual(typing_status.state, {
        next_send_start_time: undefined,
        idle_timer: undefined,
        current_recipient: null,
    });
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: true,
        timer_cleared: true,
    });

    // Call stop with nothing going on.
    call_handler(null);
    assert.deepEqual(typing_status.state, {
        next_send_start_time: undefined,
        idle_timer: undefined,
        current_recipient: null,
    });
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: false,
        timer_cleared: false,
    });

    // Start talking to alice again.
    worker.get_current_time = returns_time(50);
    call_handler("alice");
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(50 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: "alice",
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert(events.idle_callback);

    // Explicitly stop alice.
    call_handler(null);
    assert.deepEqual(typing_status.state, {
        next_send_start_time: undefined,
        idle_timer: undefined,
        current_recipient: null,
    });
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: true,
        timer_cleared: true,
    });

    // Start talking to alice again.
    worker.get_current_time = returns_time(80);
    call_handler("alice");
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(80 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: "alice",
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert(events.idle_callback);

    // Switch to an invalid conversation.
    call_handler(null);
    assert.deepEqual(typing_status.state, {
        next_send_start_time: undefined,
        idle_timer: undefined,
        current_recipient: null,
    });
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: true,
        timer_cleared: true,
    });

    // Switch to another invalid conversation.
    call_handler(null);
    assert.deepEqual(typing_status.state, {
        next_send_start_time: undefined,
        idle_timer: undefined,
        current_recipient: null,
    });
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: false,
        timer_cleared: false,
    });

    // Start talking to alice again.
    worker.get_current_time = returns_time(170);
    call_handler("alice");
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(170 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: "alice",
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert(events.idle_callback);

    // Switch to bob now.
    worker.get_current_time = returns_time(171);

    worker.notify_server_start = function (recipient) {
        assert.equal(recipient, "bob");
        events.started = true;
    };

    call_handler("bob");
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(171 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: "bob",
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: true,
        timer_cleared: true,
    });
    assert(events.idle_callback);

    // test that we correctly detect if worker.get_recipient
    // and typing_status.state.current_recipient are the same

    compose_pm_pill.get_user_ids_string = () => "1,2,3";
    typing_status.state.current_recipient = typing.get_recipient();

    const call_count = {
        maybe_ping_server: 0,
        actually_ping_server: 0,
        start_or_extend_idle_timer: 0,
        stop_last_notification: 0,
    };

    // stub functions to see how may time they are called
    for (const method of Object.keys(call_count)) {
        typing_status.__Rewire__(method, () => {
            call_count[method] += 1;
        });
    }

    // User ids of people in compose narrow doesn't change and is same as stat.current_recipient
    // so counts of function should increase except stop_last_notification
    typing_status.update(worker, typing.get_recipient());
    assert.deepEqual(call_count.maybe_ping_server, 1);
    assert.deepEqual(call_count.start_or_extend_idle_timer, 1);
    assert.deepEqual(call_count.stop_last_notification, 0);

    typing_status.update(worker, typing.get_recipient());
    assert.deepEqual(call_count.maybe_ping_server, 2);
    assert.deepEqual(call_count.start_or_extend_idle_timer, 2);
    assert.deepEqual(call_count.stop_last_notification, 0);

    // change in recipient and new_recipient should make us
    // call typing_status.stop_last_notification
    compose_pm_pill.get_user_ids_string = () => "2,3,4";
    typing_status.update(worker, typing.get_recipient());
    assert.deepEqual(call_count.maybe_ping_server, 2);
    assert.deepEqual(call_count.start_or_extend_idle_timer, 3);
    assert.deepEqual(call_count.stop_last_notification, 1);

    // Stream messages are represented as get_user_ids_string being empty
    compose_pm_pill.get_user_ids_string = () => "";
    typing_status.update(worker, typing.get_recipient());
    assert.deepEqual(call_count.maybe_ping_server, 2);
    assert.deepEqual(call_count.start_or_extend_idle_timer, 3);
    assert.deepEqual(call_count.stop_last_notification, 2);
});
