"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const compose_pm_pill = mock_esm("../src/compose_pm_pill");
const compose_state = mock_esm("../src/compose_state");
const stream_data = mock_esm("../src/stream_data");

const {set_realm} = zrequire("state_data");
const typing = zrequire("typing");
const typing_status = zrequire("../shared/src/typing_status");
const {initialize_user_settings} = zrequire("user_settings");

initialize_user_settings({user_settings: {}});
const realm = {};
set_realm(realm);

const TYPING_STARTED_WAIT_PERIOD = 10000;
const TYPING_STOPPED_WAIT_PERIOD = 5000;

function make_time(secs) {
    // make times semi-realistic
    return 1000000 + 1000 * secs;
}

function returns_time(secs) {
    return function () {
        return make_time(secs);
    };
}

run_test("basics", ({override, override_rewire}) => {
    override(realm, "realm_topics_policy", "disable_empty_topic");
    override(realm, "server_typing_started_wait_period_milliseconds", TYPING_STARTED_WAIT_PERIOD);
    override(realm, "server_typing_stopped_wait_period_milliseconds", TYPING_STOPPED_WAIT_PERIOD);

    assert.equal(typing_status.state, null);
    // invalid conversation basically does nothing
    let worker = {};
    typing_status.update(
        worker,
        null,
        realm.server_typing_started_wait_period_milliseconds,
        realm.server_typing_stopped_wait_period_milliseconds,
    );

    // Start setting up more testing state.
    const events = {};

    function set_timeout(f, delay) {
        assert.equal(delay, 5000);
        events.idle_callback = f;
        return "idle_timer_stub";
    }

    function clear_timeout() {
        events.timer_cleared = true;
    }

    set_global("setTimeout", set_timeout);
    set_global("clearTimeout", clear_timeout);

    function notify_server_start(recipient) {
        assert.deepStrictEqual(recipient, {
            message_type: "direct",
            notification_event_type: "typing",
            ids: [1, 2],
        });
        events.started = true;
    }

    function notify_server_stop(recipient) {
        assert.deepStrictEqual(recipient, {
            message_type: "direct",
            notification_event_type: "typing",
            ids: [1, 2],
        });
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
        typing_status.update(
            worker,
            new_recipient,
            realm.server_typing_started_wait_period_milliseconds,
            realm.server_typing_stopped_wait_period_milliseconds,
        );
    }

    worker = {
        get_current_time: returns_time(5),
        notify_server_start,
        notify_server_stop,
    };

    // Start talking to users having ids - 1, 2.
    call_handler({message_type: "direct", notification_event_type: "typing", ids: [1, 2]});
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(5 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {message_type: "direct", notification_event_type: "typing", ids: [1, 2]},
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert.ok(events.idle_callback);

    // type again 3 seconds later
    worker.get_current_time = returns_time(8);
    call_handler({message_type: "direct", notification_event_type: "typing", ids: [1, 2]});
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(5 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {message_type: "direct", notification_event_type: "typing", ids: [1, 2]},
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: false,
        stopped: false,
        timer_cleared: true,
    });
    assert.ok(events.idle_callback);

    // type after 15 secs, so that we can notify the server
    // again
    worker.get_current_time = returns_time(18);
    call_handler({message_type: "direct", notification_event_type: "typing", ids: [1, 2]});
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(18 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {message_type: "direct", notification_event_type: "typing", ids: [1, 2]},
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: true,
    });

    // Now call recipients idle callback that we captured earlier.
    const callback = events.idle_callback;
    clear_events();
    callback();
    assert.deepEqual(typing_status.state, null);
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: true,
        timer_cleared: true,
    });

    // Call stop with nothing going on.
    call_handler(null);
    assert.deepEqual(typing_status.state, null);
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: false,
        timer_cleared: false,
    });

    // Start talking to users again.
    worker.get_current_time = returns_time(50);
    call_handler({message_type: "direct", notification_event_type: "typing", ids: [1, 2]});
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(50 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {message_type: "direct", notification_event_type: "typing", ids: [1, 2]},
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert.ok(events.idle_callback);

    // Explicitly stop users.
    call_handler(null);
    assert.deepEqual(typing_status.state, null);
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: true,
        timer_cleared: true,
    });

    // Start talking to users again.
    worker.get_current_time = returns_time(80);
    call_handler({message_type: "direct", notification_event_type: "typing", ids: [1, 2]});
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(80 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {message_type: "direct", notification_event_type: "typing", ids: [1, 2]},
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert.ok(events.idle_callback);

    // Switch to an invalid conversation.
    call_handler(null);
    assert.deepEqual(typing_status.state, null);
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: true,
        timer_cleared: true,
    });

    // Switch to another invalid conversation.
    call_handler(null);
    assert.deepEqual(typing_status.state, null);
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: false,
        timer_cleared: false,
    });

    // Start talking to users again.
    worker.get_current_time = returns_time(170);
    call_handler({message_type: "direct", notification_event_type: "typing", ids: [1, 2]});
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(170 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {message_type: "direct", notification_event_type: "typing", ids: [1, 2]},
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert.ok(events.idle_callback);

    // Switch to new users now.
    worker.get_current_time = returns_time(171);

    worker.notify_server_start = (recipient) => {
        assert.deepStrictEqual(recipient, {
            message_type: "direct",
            notification_event_type: "typing",
            ids: [3, 4],
        });
        events.started = true;
    };

    call_handler({message_type: "direct", notification_event_type: "typing", ids: [3, 4]});
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(171 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {message_type: "direct", notification_event_type: "typing", ids: [3, 4]},
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: true,
        timer_cleared: true,
    });
    assert.ok(events.idle_callback);

    // If realm requires topics for channel messages and
    // topic is an empty string, no typing recipient is set
    override(compose_state, "get_message_type", () => "stream");
    override(compose_state, "stream_name", () => "Verona");
    override(stream_data, "get_stream_id", () => "2");
    override(stream_data, "can_use_empty_topic", () => false);
    override(compose_state, "topic", () => "");
    assert.equal(typing.get_recipient(), null);

    // test that we correctly detect if worker.get_recipient
    // and typing_status.state.current_recipient are the same

    override(compose_pm_pill, "get_user_ids_string", () => "1,2,3");
    override(compose_state, "get_message_type", () => "private");
    typing_status.state.current_recipient = typing.get_recipient();

    const call_count = {
        maybe_ping_server: 0,
        actually_ping_server: 0,
        start_or_extend_idle_timer: 0,
        stop_last_notification: 0,
    };

    // stub functions to see how may time they are called
    for (const method of Object.keys(call_count)) {
        override_rewire(typing_status, method, () => {
            call_count[method] += 1;
        });
    }

    // User ids of people in compose narrow doesn't change and is same as state.current_recipient
    // so counts of function should increase except stop_last_notification
    typing_status.update(
        worker,
        typing.get_recipient(),
        realm.server_typing_started_wait_period_milliseconds,
        realm.server_typing_stopped_wait_period_milliseconds,
    );
    assert.deepEqual(call_count.maybe_ping_server, 1);
    assert.deepEqual(call_count.start_or_extend_idle_timer, 1);
    assert.deepEqual(call_count.stop_last_notification, 0);

    typing_status.update(
        worker,
        typing.get_recipient(),
        realm.server_typing_started_wait_period_milliseconds,
        realm.server_typing_stopped_wait_period_milliseconds,
    );
    assert.deepEqual(call_count.maybe_ping_server, 2);
    assert.deepEqual(call_count.start_or_extend_idle_timer, 2);
    assert.deepEqual(call_count.stop_last_notification, 0);

    // change in recipient and new_recipient should make us
    // call typing_status.stop_last_notification
    override(compose_pm_pill, "get_user_ids_string", () => "2,3,4");
    typing_status.update(
        worker,
        typing.get_recipient(),
        realm.server_typing_started_wait_period_milliseconds,
        realm.server_typing_stopped_wait_period_milliseconds,
    );
    assert.deepEqual(call_count.maybe_ping_server, 2);
    assert.deepEqual(call_count.start_or_extend_idle_timer, 3);
    assert.deepEqual(call_count.stop_last_notification, 1);

    // Stream messages
    override(compose_state, "get_message_type", () => "stream");
    override(compose_state, "stream_name", () => "Verona");
    override(stream_data, "get_stream_id", () => "2");
    override(compose_state, "topic", () => "test topic");
    typing_status.update(
        worker,
        typing.get_recipient(),
        realm.server_typing_started_wait_period_milliseconds,
        realm.server_typing_stopped_wait_period_milliseconds,
    );
    assert.deepEqual(call_count.maybe_ping_server, 2);
    assert.deepEqual(call_count.start_or_extend_idle_timer, 4);
    assert.deepEqual(call_count.stop_last_notification, 2);
});

run_test("stream_messages", ({override, override_rewire}) => {
    override(realm, "server_typing_started_wait_period_milliseconds", TYPING_STARTED_WAIT_PERIOD);
    override(realm, "server_typing_stopped_wait_period_milliseconds", TYPING_STOPPED_WAIT_PERIOD);
    override_rewire(typing_status, "state", null);

    let worker = {};
    const events = {};

    function set_timeout(f, delay) {
        assert.equal(delay, 5000);
        events.idle_callback = f;
        return "idle_timer_stub";
    }

    function clear_timeout() {
        events.timer_cleared = true;
    }

    set_global("setTimeout", set_timeout);
    set_global("clearTimeout", clear_timeout);

    function notify_server_start(recipient) {
        assert.deepStrictEqual(recipient, {
            message_type: "stream",
            notification_event_type: "typing",
            stream_id: 3,
            topic: "test",
        });
        events.started = true;
    }

    function notify_server_stop(recipient) {
        assert.deepStrictEqual(recipient, {
            message_type: "stream",
            notification_event_type: "typing",
            stream_id: 3,
            topic: "test",
        });
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
        typing_status.update(
            worker,
            new_recipient,
            realm.server_typing_started_wait_period_milliseconds,
            realm.server_typing_stopped_wait_period_milliseconds,
        );
    }

    worker = {
        get_current_time: returns_time(5),
        notify_server_start,
        notify_server_stop,
    };

    // Start typing stream message
    call_handler({
        message_type: "stream",
        notification_event_type: "typing",
        stream_id: 3,
        topic: "test",
    });
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(5 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {
            message_type: "stream",
            notification_event_type: "typing",
            stream_id: 3,
            topic: "test",
        },
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert.ok(events.idle_callback);

    // type again 3 seconds later. Covers 'same_stream_and_topic' codepath.
    worker.get_current_time = returns_time(8);
    call_handler({
        message_type: "stream",
        notification_event_type: "typing",
        stream_id: 3,
        topic: "test",
    });
    assert.deepEqual(typing_status.state, {
        next_send_start_time: make_time(5 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {
            message_type: "stream",
            notification_event_type: "typing",
            stream_id: 3,
            topic: "test",
        },
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: false,
        stopped: false,
        timer_cleared: true,
    });
    assert.ok(events.idle_callback);

    // Explicitly stop.
    call_handler(null);
    assert.deepEqual(typing_status.state, null);
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: true,
        timer_cleared: true,
    });
});

run_test("edit_messages", ({override_rewire}) => {
    override_rewire(typing_status, "state", null);

    let worker = {};
    const events = {};
    const message_id = 7;

    function set_timeout(f, delay) {
        assert.equal(delay, 5000);
        events.idle_callback = f;
        return "idle_timer_stub";
    }

    function clear_timeout() {
        events.timer_cleared = true;
    }

    set_global("setTimeout", set_timeout);
    set_global("clearTimeout", clear_timeout);

    function notify_server_editing_start(recipient) {
        assert.deepStrictEqual(recipient, {
            notification_event_type: "typing_message_edit",
            message_id,
        });
        events.started = true;
    }

    function notify_server_editing_stop(recipient) {
        assert.deepStrictEqual(recipient, {
            notification_event_type: "typing_message_edit",
            message_id,
        });
        events.stopped = true;
    }

    function clear_events() {
        events.idle_callback = undefined;
        events.started = false;
        events.stopped = false;
        events.timer_cleared = false;
    }

    function call_handler_start(new_recipient) {
        clear_events();
        typing_status.update_editing_status(
            worker,
            new_recipient,
            "start",
            TYPING_STARTED_WAIT_PERIOD,
            TYPING_STOPPED_WAIT_PERIOD,
        );
    }

    function call_handler_stop(new_recipient) {
        clear_events();
        typing_status.update_editing_status(
            worker,
            new_recipient,
            "stop",
            TYPING_STARTED_WAIT_PERIOD,
            TYPING_STOPPED_WAIT_PERIOD,
        );
    }

    worker = {
        get_current_time: returns_time(5),
        notify_server_editing_start,
        notify_server_editing_stop,
    };

    // Start typing stream message
    call_handler_start({
        notification_event_type: "typing_message_edit",
        message_id,
    });
    assert.deepEqual(typing_status.editing_state.get(message_id), {
        next_send_start_time: make_time(5 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {
            notification_event_type: "typing_message_edit",
            message_id,
        },
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert.ok(events.idle_callback);

    worker.get_current_time = returns_time(8);
    call_handler_start({
        notification_event_type: "typing_message_edit",
        message_id,
    });
    assert.deepEqual(typing_status.editing_state.get(message_id), {
        next_send_start_time: make_time(5 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {
            notification_event_type: "typing_message_edit",
            message_id,
        },
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: false,
        stopped: false,
        timer_cleared: true,
    });
    assert.ok(events.idle_callback);

    worker.get_current_time = returns_time(18);
    call_handler_start({
        notification_event_type: "typing_message_edit",
        message_id,
    });
    assert.deepEqual(typing_status.editing_state.get(message_id), {
        next_send_start_time: make_time(18 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {
            notification_event_type: "typing_message_edit",
            message_id,
        },
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: true,
    });
    assert.ok(events.idle_callback);

    // Now call recipients idle callback that we captured earlier.
    const callback = events.idle_callback;
    clear_events();
    callback();
    assert.deepEqual(typing_status.editing_state.get(message_id), undefined);
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: true,
        timer_cleared: true,
    });

    // Start editing message again.
    worker.get_current_time = returns_time(50);
    call_handler_start({
        notification_event_type: "typing_message_edit",
        message_id,
    });
    assert.deepEqual(typing_status.editing_state.get(message_id), {
        next_send_start_time: make_time(50 + 10),
        idle_timer: "idle_timer_stub",
        current_recipient: {
            notification_event_type: "typing_message_edit",
            message_id,
        },
    });
    assert.deepEqual(events, {
        idle_callback: events.idle_callback,
        started: true,
        stopped: false,
        timer_cleared: false,
    });
    assert.ok(events.idle_callback);

    // Explicitly stop.
    call_handler_stop({
        notification_event_type: "typing_message_edit",
        message_id,
    });
    assert.deepEqual(typing_status.editing_state.get(message_id), undefined);
    assert.deepEqual(events, {
        idle_callback: undefined,
        started: false,
        stopped: true,
        timer_cleared: true,
    });
});
