"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

zrequire("unread");
zrequire("unread_ops");
zrequire("message_flags");

set_global("ui", {});
set_global("channel", {});
set_global("starred_messages", {
    add: () => {},
    remove: () => {},
});

run_test("starred", () => {
    const message = {
        id: 50,
    };
    set_global("current_msg_list", {
        all_messages: () => [message],
        is_search: () => false,
    });
    let ui_updated;

    ui.update_starred_view = () => {
        ui_updated = true;
    };

    let posted_data;

    channel.post = (opts) => {
        assert.equal(opts.url, "/json/messages/flags");
        posted_data = opts.data;
    };

    message_flags.toggle_starred_and_update_server(message);

    assert(ui_updated);

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

    assert(ui_updated);

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
run_test("read", () => {
    // Way to capture posted info in every request
    let channel_post_opts;
    channel.post = (opts) => {
        channel_post_opts = opts;
    };

    // For testing purpose limit the batch size value to 5 instead of 1000
    message_flags._unread_batch_size = 5;
    let msgs_to_flag_read = [
        {locally_echoed: false, id: 1},
        {locally_echoed: false, id: 2},
        {locally_echoed: false, id: 3},
        {locally_echoed: false, id: 4},
        {locally_echoed: false, id: 5},
        {locally_echoed: false, id: 6},
        {locally_echoed: false, id: 7},
    ];
    message_flags.send_read(msgs_to_flag_read);
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
    message_flags.send_read(msgs_to_flag_read);
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
