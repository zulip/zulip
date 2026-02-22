"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

mock_esm("../src/message_feed_loading", {
    hide_indicators() {},
});

const narrow_banner = mock_esm("../src/narrow_banner.ts");

const {Filter} = zrequire("filter");
const {MessageListData} = zrequire("message_list_data");
const message_fetch = zrequire("message_fetch");

run_test("get_parameters_for_message_fetch_api date anchor", () => {
    const msg_list_data = new MessageListData({
        excludes_muted_topics: false,
        filter: new Filter([]),
    });

    const anchor_date = new Date("2024-01-02T00:00:00.000Z").toISOString();
    const params = message_fetch.get_parameters_for_message_fetch_api({
        anchor: "date",
        anchor_date,
        num_before: 0,
        num_after: 0,
        cont() {},
        msg_list_data,
    });
    assert.equal(params.anchor, "date");
    assert.equal(params.anchor_date, anchor_date);

    blueslip.expect("error", "Missing anchor_date for date anchor fetch");
    const missing_date = message_fetch.get_parameters_for_message_fetch_api({
        anchor: "date",
        num_before: 0,
        num_after: 0,
        cont() {},
        msg_list_data,
    });
    assert.equal(missing_date.anchor_date, undefined);
});

run_test("load_messages error handling - server error message", ({override, override_rewire}) => {
    // Mock dependencies
    override(narrow_banner, "show_error_message", () => {});
    override(narrow_banner, "show_empty_narrow_message", () => {});
    
    const message_lists = {};
    override_rewire(message_fetch, "message_lists", message_lists);

    let show_error_message_called = false;
    let show_empty_narrow_message_called = false;
    let error_message_text = null;

    override(narrow_banner, "show_error_message", (msg) => {
        show_error_message_called = true;
        error_message_text = msg;
    });

    override(narrow_banner, "show_empty_narrow_message", () => {
        show_empty_narrow_message_called = true;
    });

    const msg_list_data = new MessageListData({
        excludes_muted_topics: false,
        filter: new Filter([]),
    });

    const msg_list = {
        data: msg_list_data,
        is_combined_feed_view: false,
        visibly_empty() {
            return true;
        },
    };

    message_lists.current = msg_list;

    // Simulate a 400 error with a server-provided error message
    const xhr = {
        status: 400,
        responseJSON: {
            msg: "Too many messages requested (maximum 5000)",
        },
    };

    // Call the error handler directly
    const opts = {
        msg_list,
        msg_list_data,
        num_before: 0,
        num_after: 0,
    };

    // Trigger error by calling load_messages with mocked channel.get that calls error callback
    override(message_fetch, "channel", {
        get(config) {
            config.error(xhr);
        },
    });

    message_fetch.load_messages(opts);

    // Verify show_error_message was called with the correct message
    assert.ok(show_error_message_called, "show_error_message should be called");
    assert.equal(error_message_text, "Too many messages requested (maximum 5000)");
    assert.ok(!show_empty_narrow_message_called, "show_empty_narrow_message should not be called");
});

run_test("load_messages error handling - no error message fallback", ({override, override_rewire}) => {
    // Mock dependencies
    override(narrow_banner, "show_error_message", () => {});
    override(narrow_banner, "show_empty_narrow_message", () => {});
    
    const message_lists = {};
    override_rewire(message_fetch, "message_lists", message_lists);

    let show_error_message_called = false;
    let show_empty_narrow_message_called = false;

    override(narrow_banner, "show_error_message", () => {
        show_error_message_called = true;
    });

    override(narrow_banner, "show_empty_narrow_message", () => {
        show_empty_narrow_message_called = true;
    });

    const msg_list_data = new MessageListData({
        excludes_muted_topics: false,
        filter: new Filter([]),
    });

    const msg_list = {
        data: msg_list_data,
        is_combined_feed_view: false,
        visibly_empty() {
            return true;
        },
    };

    message_lists.current = msg_list;

    // Simulate a 400 error without a server-provided error message
    const xhr = {
        status: 400,
        responseJSON: {},
    };

    const opts = {
        msg_list,
        msg_list_data,
        num_before: 0,
        num_after: 0,
    };

    override(message_fetch, "channel", {
        get(config) {
            config.error(xhr);
        },
    });

    message_fetch.load_messages(opts);

    // Verify show_empty_narrow_message was called as fallback
    assert.ok(!show_error_message_called, "show_error_message should not be called");
    assert.ok(show_empty_narrow_message_called, "show_empty_narrow_message should be called");
});
