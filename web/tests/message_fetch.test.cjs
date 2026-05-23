"use strict";

const assert = require("node:assert/strict");

const {zrequire, mock_esm} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const {Filter} = zrequire("filter");
const {MessageListData} = zrequire("message_list_data");
const channel = mock_esm("../src/channel");
const message_fetch = zrequire("message_fetch");
const message_lists = zrequire("message_lists");
const narrow_banner = mock_esm("../src/narrow_banner");
const popup_banners = mock_esm("../src/popup_banners");

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

run_test("load_messages uses server msg for 400 error in empty narrow", ({override}) => {
    const msg_list_data = new MessageListData({
        excludes_muted_topics: false,
        filter: new Filter([{operator: "stream", operand: "missing-stream"}]),
    });

    const msg_list = {
        data: msg_list_data,
        is_combined_feed_view: false,
        visibly_empty: () => true,
    };
    message_lists.set_current(msg_list);

    let shown_error_message;
    override(narrow_banner, "show_error_narrow_message", (error_message) => {
        shown_error_message = error_message;
    });
    override(popup_banners, "close_connection_error_popup_banner", () => {});

    let showed_empty_banner = false;
    override(
        narrow_banner,
        "show_empty_narrow_message",
        () => {
            showed_empty_banner = true;
        },
        {unused: false},
    );

    override(channel, "get", (args) => {
        args.error({
            status: 400,
            responseJSON: {msg: "No channel with name 'missing-stream'"},
        });
    });

    message_fetch.load_messages({
        anchor: "newest",
        num_before: 0,
        num_after: 20,
        cont() {},
        msg_list_data,
        msg_list,
    });

    assert.equal(shown_error_message, "No channel with name 'missing-stream'");
    assert.equal(showed_empty_banner, false);
    message_lists.set_current(undefined);
});
