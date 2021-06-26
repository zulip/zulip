"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, with_field, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const channel = mock_esm("../../static/js/channel");
const ui = mock_esm("../../static/js/ui");

mock_esm("../../static/js/starred_messages", {
    add: () => {},
    get_starred_msg_ids: () => [1, 2, 3, 4, 5],
    remove: () => {},
});

const message_flags = zrequire("message_flags");

run_test("starred", ({override}) => {
    const message = {
        id: 50,
    };
    let ui_updated;

    override(ui, "update_starred_view", () => {
        ui_updated = true;
    });

    let posted_data;

    override(channel, "post", (opts) => {
        assert.equal(opts.url, "/json/messages/flags");
        posted_data = opts.data;
    });

    message_flags.toggle_starred_and_update_server(message);

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

    message_flags.toggle_starred_and_update_server(message);

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

    message_flags.toggle_starred_and_update_server(locally_echoed_message);

    // ui.update_starred_view not called

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
            {operator: "stream", operand: 20},
            {operator: "topic", operand: "topic"},
            {operator: "is", operand: "starred"},
        ]),
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
        with_field(message_flags, "_unread_batch_size", 5, () => {
            message_flags.send_read(messages);
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
        idempotent: true,
        data: {
            messages: "[1,2,3,4,5]",
            op: "add",
            flag: "read",
        },
        success: channel_post_opts.success,
    });

    // Mock successful flagging of ids
    let success_response_data = {
        messages: [1, 2, 3, 4, 5],
    };
    channel_post_opts.success(success_response_data);
    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        idempotent: true,
        data: {
            messages: "[6,7]",
            op: "add",
            flag: "read",
        },
        success: channel_post_opts.success,
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
        idempotent: true,
        data: {
            messages: "[3,4,5,6,7]",
            op: "add",
            flag: "read",
        },
        success: channel_post_opts.success,
    });

    // Messages still not acked yet
    const events = {};
    const stub_delay = 100;
    function set_timeout(f, delay) {
        assert.equal(delay, stub_delay);
        events.f = f;
        events.timer_set = true;
        return;
    }
    set_global("setTimeout", set_timeout);
    // Mock successful flagging of ids
    success_response_data = {
        messages: [3, 4, 5, 6, 7],
    };
    channel_post_opts.success(success_response_data);
    assert.ok(events.timer_set);

    // Mark them non local
    local_msg_1.locally_echoed = false;
    local_msg_2.locally_echoed = false;

    // Mock successful flagging of ids
    success_response_data = {
        messages: [3, 4, 5, 6, 7],
    };
    channel_post_opts.success(success_response_data);

    // Former locally echoed messages flagging retried
    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        idempotent: true,
        data: {
            messages: "[1,2]",
            op: "add",
            flag: "read",
        },
        success: channel_post_opts.success,
    });
});

run_test("read_empty_data", ({override}) => {
    // Way to capture posted info in every request
    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    // For testing purpose limit the batch size value to 5 instead of 1000
    function send_read(messages) {
        with_field(message_flags, "_unread_batch_size", 5, () => {
            message_flags.send_read(messages);
        });
    }

    // send read to obtain success callback
    send_read({locally_echoed: false, id: 1});

    // verify early return on empty data
    const success_callback = channel_post_opts.success;
    channel_post_opts = {};
    let empty_data;
    success_callback(empty_data);
    assert.deepEqual(channel_post_opts, {});
    empty_data = {messages: undefined};
    success_callback(empty_data);
    assert.deepEqual(channel_post_opts, {});
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
        idempotent: true,
        data: {
            messages: "[5]",
            op: "add",
            flag: "collapsed",
        },
    });

    message_flags.save_uncollapsed(msg);

    assert.deepEqual(channel_post_opts, {
        url: "/json/messages/flags",
        idempotent: true,
        data: {
            messages: "[5]",
            op: "remove",
            flag: "collapsed",
        },
    });
});
