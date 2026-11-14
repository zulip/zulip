"use strict";

const assert = require("node:assert/strict");

const {clock, mock_esm, with_overrides, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const channel = mock_esm("../src/channel");
const message_live_update = mock_esm("../src/message_live_update");

mock_esm("../src/starred_messages", {
    add() {},
    get_count: () => 5,
    get_starred_msg_ids: () => [1, 2, 3, 4, 5],
    remove() {},
});
mock_esm("../src/left_sidebar_navigation_area", {
    update_starred_count() {},
});

const message_flags = zrequire("message_flags");
const starred_messages_ui = zrequire("starred_messages_ui");
const {initialize_user_settings} = zrequire("user_settings");

initialize_user_settings({user_settings: {}});

run_test("starred", ({override}) => {
    const message = {
        id: 50,
    };
    let ui_updated;

    override(message_live_update, "update_starred_view", () => {
        ui_updated = true;
    });

    let posted_data;

    override(channel, "post", (opts) => {
        assert.equal(opts.url, "/json/messages/flags");
        posted_data = opts.data;
    });

    starred_messages_ui.toggle_starred_and_update_server(message);

    assert.ok(ui_updated);

    assert.deepEqual(posted_data, {
        messages: "[50]",
        flag: "starred",
        op: "add",
    });

    assert.deepEqual(message, {
        id: 50,
        starred: true,
    });

    ui_updated = false;

    starred_messages_ui.toggle_starred_and_update_server(message);

    assert.ok(ui_updated);

    assert.deepEqual(posted_data, {
        messages: "[50]",
        flag: "starred",
        op: "remove",
    });

    assert.deepEqual(message, {
        id: 50,
        starred: false,
    });
});

run_test("starring local echo", () => {
    // verify early return for locally echoed message
    const locally_echoed_message = {
        id: 51,
        starred: false,
        locally_echoed: true,
    };

    starred_messages_ui.toggle_starred_and_update_server(locally_echoed_message);

    // message_live_update.update_starred_view not called

    // channel post request not made

    // starred flag unchanged
    assert.deepEqual(locally_echoed_message, {
        id: 51,
        locally_echoed: true,
        starred: false,
    });
});

run_test("unstar_all", ({override}) => {
    // Way to capture posted info in every request
    let posted_data;
    override(channel, "post", (opts) => {
        assert.equal(opts.url, "/json/messages/flags");
        posted_data = opts.data;
    });

    // we've set get_starred_msg_ids to return [1, 2, 3, 4, 5]
    const expected_data = {messages: "[1,2,3,4,5]", flag: "starred", op: "remove"};

    message_flags.unstar_all_messages();

    assert.deepEqual(posted_data, expected_data);
});

run_test("unstar_all_in_topic", ({override}) => {
    // Way to capture posted info in every request
    let channel_post_opts;
    let channel_get_opts;

    override(channel, "get", (opts) => {
        assert.equal(opts.url, "/json/messages");
        channel_get_opts = opts;
        opts.success({
            messages: [{id: 2}, {id: 3}, {id: 5}],
        });
    });

    override(channel, "post", (opts) => {
        assert.equal(opts.url, "/json/messages/flags");
        channel_post_opts = opts;
    });

    message_flags.unstar_all_messages_in_topic(20, "topic");

    assert.deepEqual(channel_get_opts.data, {
        anchor: "newest",
        num_before: 1000,
        num_after: 0,
        narrow: JSON.stringify([
            {operator: "channel", operand: 20},
            {operator: "topic", operand: "topic"},
            {operator: "is", operand: "starred"},
        ]),
        allow_empty_topic_name: true,
    });

    assert.deepEqual(channel_post_opts.data, {
        messages: "[2,3,5]",
        flag: "starred",
        op: "remove",
    });
});

run_test("read", ({override}) => {
    // Way to capture posted info in every request
    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    // For testing purpose limit the batch size value to 5 instead of 1000
    function send_read(messages) {
        with_overrides(({override_rewire}) => {
            override_rewire(message_flags, "_unread_batch_size", 5);
            message_flags.send_read.add(messages);
        });
    }

    let msgs_to_flag_read = [
        {locally_echoed: false, id: 1},
        {locally_echoed: false, id: 2},
        {locally_echoed: false, id: 3},
        {locally_echoed: false, id: 4},
        {locally_echoed: false, id: 5},
        {locally_echoed: false, id: 6},
        {locally_echoed: false, id: 7},
    ];
    send_read(msgs_to_flag_read);
    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        data: {
            messages: "[1,2,3,4,5]",
            op: "add",
            flag: "read",
        },
        success: channel_post_opts.success,
        error: channel_post_opts.error,
    });

    // Mock successful flagging of ids
    let success_response_data = {
        messages: [1, 2, 3, 4, 5],
    };
    channel_post_opts.success(success_response_data);
    clock.runAll();
    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        data: {
            messages: "[6,7]",
            op: "add",
            flag: "read",
        },
        success: channel_post_opts.success,
        error: channel_post_opts.error,
    });
    success_response_data = {
        messages: [6, 7],
    };
    channel_post_opts.success(success_response_data);

    // Don't flag locally echoed messages as read
    const local_msg_1 = {locally_echoed: true, id: 1};
    const local_msg_2 = {locally_echoed: true, id: 2};
    msgs_to_flag_read = [
        local_msg_1,
        local_msg_2,
        {locally_echoed: false, id: 3},
        {locally_echoed: false, id: 4},
        {locally_echoed: false, id: 5},
        {locally_echoed: false, id: 6},
        {locally_echoed: false, id: 7},
    ];
    send_read(msgs_to_flag_read);
    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        data: {
            messages: "[3,4,5,6,7]",
            op: "add",
            flag: "read",
        },
        success: channel_post_opts.success,
        error: channel_post_opts.error,
    });

    // Messages still not acked yet
    // Mock successful flagging of ids
    success_response_data = {
        messages: [3, 4, 5, 6, 7],
    };
    channel_post_opts.success(success_response_data);
    clock.tick(1100);

    // Mark them non-local
    local_msg_1.locally_echoed = false;
    local_msg_2.locally_echoed = false;
    clock.runAll();

    // Former locally echoed messages flagging retried
    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        data: {
            messages: "[1,2]",
            op: "add",
            flag: "read",
        },
        success: channel_post_opts.success,
        error: channel_post_opts.error,
    });
    const send_read_success = channel_post_opts.success;

    msgs_to_flag_read = [1, 2, 3, 4, 5];
    message_flags.mark_as_read(msgs_to_flag_read);
    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        data: {
            messages: "[1,2,3,4,5]",
            op: "add",
            flag: "read",
        },
    });

    // Drain the locally_echoed retry batch [1, 2] so the next test starts
    // with an idle state and clean queue.
    send_read_success({messages: [1, 2]});
    clock.runAll();
    clock.reset();
});

run_test("send_read.remove_from_queue", ({override}) => {
    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    function send_read(messages) {
        with_overrides(({override_rewire}) => {
            override_rewire(message_flags, "_unread_batch_size", 5);
            message_flags.send_read.add(messages);
        });
    }

    // Enqueue messages 21..25.
    send_read([
        {locally_echoed: false, id: 21},
        {locally_echoed: false, id: 22},
        {locally_echoed: false, id: 23},
        {locally_echoed: false, id: 24},
        {locally_echoed: false, id: 25},
    ]);

    // At this point, channel.post was called with the batch.
    assert.ok(channel_post_opts.data.messages.includes("21"));

    // Enqueue more messages.
    send_read([
        {locally_echoed: false, id: 26},
        {locally_echoed: false, id: 27},
    ]);

    // Remove messages 24 and 27 from the queue.
    message_flags.send_read.remove_from_queue([24, 27]);

    // Simulate success for the first batch [21..25]; this removes
    // messages [21, 22, 23, 25] from the queue (24 was already
    // removed above) and schedules the next batch.
    channel_post_opts.success({messages: [21, 22, 23, 24, 25]});

    // Advance past the throttle window so the next batch fires.
    clock.tick(1100);

    // The remaining queue should only contain [26].
    assert.equal(channel_post_opts.data.messages, "[26]");

    // Drain the remaining batch and reset timers for the next test.
    channel_post_opts.success({messages: [26]});
    clock.runAll();
    clock.reset();
});

run_test("send_read empty queue after remove_from_queue does not spin", ({disallow}) => {
    disallow(channel, "post");

    message_flags.send_read.add([{locally_echoed: false, id: 999}]);
    message_flags.send_read.remove_from_queue([999]);

    // Advance clock past the 1000ms throttle.
    clock.tick(1100);

    // Should not spin indefinitely with setTimeout(start, 100).
    clock.runAll();
    clock.reset();
});

run_test("send_read does not initiate concurrent request while in_flight", ({override}) => {
    let call_count = 0;
    let channel_post_opts;
    override(channel, "post", (opts) => {
        call_count += 1;
        channel_post_opts = opts;
    });

    function send_read(messages) {
        with_overrides(({override_rewire}) => {
            override_rewire(message_flags, "_unread_batch_size", 5);
            message_flags.send_read.add(messages);
        });
    }

    // Start first request
    send_read([{locally_echoed: false, id: 51}]);
    clock.tick(1100);
    assert.equal(call_count, 1);
    assert.equal(message_flags.send_read.is_in_flight(), true);

    // Queue more messages and advance clock while first request is still in flight
    send_read([{locally_echoed: false, id: 52}]);
    clock.tick(1100);
    // Should NOT have made a second concurrent request while first is in-flight
    assert.equal(call_count, 1);

    // Complete first request; since throttle window elapsed, start() triggers
    // the next batch immediately.
    channel_post_opts.success({messages: [51]});
    assert.equal(call_count, 2);
    assert.equal(channel_post_opts.data.messages, "[52]");
    assert.equal(message_flags.send_read.is_in_flight(), true);

    channel_post_opts.success({messages: [52]});
    assert.equal(message_flags.send_read.is_in_flight(), false);
    clock.runAll();
    clock.reset();
});

run_test("send_read.is_in_flight", ({override}) => {
    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    function send_read(messages) {
        with_overrides(({override_rewire}) => {
            override_rewire(message_flags, "_unread_batch_size", 5);
            message_flags.send_read.add(messages);
        });
    }

    assert.equal(message_flags.send_read.is_in_flight(), false);

    send_read([{locally_echoed: false, id: 31}]);
    clock.tick(1100);

    assert.equal(message_flags.send_read.is_in_flight(), true);

    channel_post_opts.success({messages: [31]});

    assert.equal(message_flags.send_read.is_in_flight(), false);

    clock.runAll();
    clock.reset();
});

run_test("send_read.wait_for_in_flight", ({override}) => {
    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    function send_read(messages) {
        with_overrides(({override_rewire}) => {
            override_rewire(message_flags, "_unread_batch_size", 5);
            message_flags.send_read.add(messages);
        });
    }

    // When not in flight, callback is invoked immediately.
    let called_when_idle = false;
    message_flags.send_read.wait_for_in_flight(() => {
        called_when_idle = true;
    });
    assert.equal(called_when_idle, true);

    // Start an in-flight request.
    send_read([{locally_echoed: false, id: 41}]);
    clock.tick(1100);
    assert.equal(message_flags.send_read.is_in_flight(), true);

    // While in flight, callback is queued.
    let called_after_success = false;
    message_flags.send_read.wait_for_in_flight(() => {
        called_after_success = true;
    });
    assert.equal(called_after_success, false);

    // On success, the queued callback is invoked.
    channel_post_opts.success({messages: [41]});
    assert.equal(called_after_success, true);
    assert.equal(message_flags.send_read.is_in_flight(), false);

    // Advance clock past throttle before queuing another batch.
    clock.tick(1100);

    // Also verify error handler notifies waiters.
    send_read([{locally_echoed: false, id: 42}]);
    clock.tick(1100);
    assert.equal(message_flags.send_read.is_in_flight(), true);

    let called_after_error = false;
    message_flags.send_read.wait_for_in_flight(() => {
        called_after_error = true;
    });
    assert.equal(called_after_error, false);

    channel_post_opts.error();
    assert.equal(called_after_error, true);
    assert.equal(message_flags.send_read.is_in_flight(), false);

    message_flags.send_read.remove_from_queue([42]);
    clock.runAll();
    clock.reset();
});

run_test("read_empty_data", ({override}) => {
    // Way to capture posted info in every request
    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    // For testing purpose limit the batch size value to 5 instead of 1000
    function send_read(messages) {
        with_overrides(({override_rewire}) => {
            override_rewire(message_flags, "_unread_batch_size", 5);
            message_flags.send_read.add(messages);
        });
    }

    // send read to obtain success callback
    send_read([{locally_echoed: false, id: 1}]);
    // Ensure the throttled server_request fires.
    clock.tick(1100);

    // verify early return on empty data
    const success_callback = channel_post_opts.success;
    channel_post_opts = {};
    let empty_data;
    success_callback(empty_data);
    assert.deepEqual(channel_post_opts, {});
    empty_data = {messages: undefined};
    success_callback(empty_data);
    assert.deepEqual(channel_post_opts, {});

    message_flags.send_read.remove_from_queue([1]);
    clock.runAll();
    clock.reset();
});

run_test("collapse_and_uncollapse", ({override}) => {
    // Way to capture posted info in every request
    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    const msg = {id: 5};

    message_flags.save_collapsed(msg);

    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        data: {
            messages: "[5]",
            op: "add",
            flag: "collapsed",
        },
    });

    message_flags.save_uncollapsed(msg);

    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        data: {
            messages: "[5]",
            op: "remove",
            flag: "collapsed",
        },
    });
});

run_test("mark_as_unread", ({override}) => {
    // Way to capture posted info in every request
    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    const msg = {id: 5};

    message_flags.mark_as_unread([msg.id]);

    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        data: {
            messages: "[5]",
            op: "remove",
            flag: "read",
        },
    });
});
