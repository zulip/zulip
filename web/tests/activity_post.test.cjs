"use strict";

const assert = require("node:assert/strict");

const {clock, mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {noop, run_test} = require("./lib/test.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

mock_esm("../src/electron_bridge");
mock_esm("../src/watchdog", {
    check_for_unsuspend: noop,
});

const channel = mock_esm("../src/channel");
const presence = mock_esm("../src/presence");

set_global("document", {hasFocus: () => true});

const activity = zrequire("activity");
const server_time = zrequire("server_time");

run_test("send_presence_to_server (spectator)", ({override}) => {
    override(page_params, "is_spectator", true);
    activity.send_presence_to_server();
});

run_test("send_presence_to_server (no redraw)", ({override}) => {
    let success_function;

    assert.equal(activity.new_user_input, true);

    override(channel, "post", ({url, data, success}) => {
        success_function = success;
        assert.equal(url, "/json/users/me/presence");
        assert.deepEqual(data, {
            status: "active",
            ping_only: true,
            new_user_input: true,
            last_update_id: 42,
        });
    });

    override(presence, "presence_last_update_id", 42);
    activity.send_presence_to_server();

    const response = {
        presences: {},
        msg: "",
        result: "success",
        server_timestamp: 0,
        presence_last_update_id: -1,
    };

    success_function(response);
    assert.equal(activity.new_user_input, false);
});

run_test("send_presence_to_server (redraw)", ({override}) => {
    let success_function;

    activity.set_new_user_input(true);
    assert.equal(activity.new_user_input, true);

    override(channel, "post", ({url, data, success}) => {
        success_function = success;
        assert.equal(url, "/json/users/me/presence");
        assert.deepEqual(data, {
            status: "active",
            ping_only: false,
            new_user_input: true,
            last_update_id: 77,
        });
    });

    let num_redraw_callbacks = 0;

    function redraw() {
        num_redraw_callbacks += 1;
    }

    override(presence, "presence_last_update_id", 77);
    activity.send_presence_to_server(redraw);

    const response = {
        presences: {},
        msg: "",
        result: "success",
        server_timestamp: 9999,
        presence_last_update_id: 78,
    };

    override(presence, "set_info", (presences, server_timestamp, presence_last_update_id) => {
        assert.deepEqual(presences, {});
        assert.deepEqual(server_timestamp, 9999);
        assert.deepEqual(presence_last_update_id, 78);
    });

    success_function(response);
    assert.equal(activity.new_user_input, false);
    assert.equal(num_redraw_callbacks, 1);
});

run_test("send_presence_to_server updates server_time with RTT", ({override}) => {
    server_time._reset_for_testing();
    clock.setSystemTime(1000 * 1000);

    let success_function;
    override(channel, "post", ({success}) => {
        success_function = success;
    });

    activity.send_presence_to_server();

    // Advance 400ms (0.4s RTT)
    clock.tick(400);

    const response = {
        presences: {},
        msg: "",
        result: "success",
        server_timestamp: 2000,
        presence_last_update_id: -1,
    };

    success_function(response);

    // After 0.4s RTT, at arrival (client t = 1000.4s), server_time.now()
    // reflects server_timestamp + 0.2s = 2000.2s.
    assert.equal(Math.round(server_time.now() * 10) / 10, 2000.2);
    server_time._reset_for_testing();
});
