"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {noop, run_test} = require("./lib/test.cjs");

const activity = mock_esm("../src/activity");
const buddy_list_presence = mock_esm("../src/buddy_list_presence");
const scroll_util = mock_esm("../src/scroll_util");
const pm_list = mock_esm("../src/pm_list");
const util = mock_esm("../src/util");

const state_data = zrequire("state_data");
const activity_ui = zrequire("activity_ui");

run_test("redraw", ({override, override_rewire}) => {
    override_rewire(activity_ui, "build_user_sidebar", noop);
    activity_ui.set_cursor_and_filter();
    override(pm_list, "update_private_messages", noop);
    override(buddy_list_presence, "update_indicators", noop);

    activity_ui.redraw();
});

run_test("initialize", ({override, override_rewire}) => {
    const realm = make_realm();
    state_data.set_realm(realm);

    override(realm, "server_presence_ping_interval_seconds", 42);

    override_rewire(activity_ui, "set_cursor_and_filter", noop);
    override_rewire(activity_ui, "build_user_sidebar", noop);

    override(scroll_util, "get_scroll_element", (selector) => {
        assert.equal(selector.selector, "#buddy_list_wrapper");
        return {
            on(action, callback) {
                assert.equal(action, "scroll");
                // We don't test the actual logic of the scroll
                // handler here.  We did our job to set it up.
                assert.ok(callback !== undefined);
            },
        };
    });

    let expected_redraw;
    let num_presence_calls = 0;

    override(activity, "send_presence_to_server", (redraw) => {
        num_presence_calls += 1;
        assert.equal(redraw, expected_redraw);
    });

    let f_to_call_periodically;

    override(util, "call_function_periodically", (f, delay) => {
        f_to_call_periodically = f;
        assert.equal(delay, 42000);
    });

    let my_email = "";

    function narrow_by_email(email) {
        my_email = email;
    }

    activity_ui.initialize({narrow_by_email});

    assert.equal(my_email, "");
    activity_ui.get_narrow_by_email_function_for_test_code()("alice@example.com");
    assert.equal(my_email, "alice@example.com");

    // Simulate the subsequent calls to
    // activity.send_presence_to_server.
    expected_redraw = activity_ui.redraw;

    assert.equal(num_presence_calls, 1);
    f_to_call_periodically();
    f_to_call_periodically();
    f_to_call_periodically();
    f_to_call_periodically();
    f_to_call_periodically();
    assert.equal(num_presence_calls, 6);
    f_to_call_periodically();
    f_to_call_periodically();
    f_to_call_periodically();
    f_to_call_periodically();
    f_to_call_periodically();
    assert.equal(num_presence_calls, 11);
});
