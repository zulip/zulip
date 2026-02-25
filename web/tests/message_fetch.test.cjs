"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {noop, run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const message_feed_loading = mock_esm("../src/message_feed_loading");
const narrow_banner = mock_esm("../src/narrow_banner");
const popup_banners = mock_esm("../src/popup_banners");
const ui_report = mock_esm("../src/ui_report");

const channel = mock_esm("../src/channel");
const {Filter} = zrequire("filter");
const {MessageListData} = zrequire("message_list_data");
const message_lists = zrequire("message_lists");
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

run_test("load_messages: 400 surfaces server error message", ({disallow, override}) => {
    const msg_list_data = new MessageListData({
        excludes_muted_topics: false,
        filter: new Filter([]),
    });
    let hide_indicators_called = false;
    let error_message_html;

    override(message_feed_loading, "hide_indicators", () => {
        hide_indicators_called = true;
    });
    override(ui_report, "generic_embed_error", (message_html) => {
        error_message_html = message_html;
    });
    override(narrow_banner, "hide_empty_narrow_message", noop);
    disallow(narrow_banner, "show_empty_narrow_message");
    override(popup_banners, "close_connection_error_popup_banner", noop);
    override(channel, "get", (opts) => {
        opts.error({
            status: 400,
            responseJSON: {msg: "Too many <messages> requested (maximum 5000)"},
        });
    });
    override(
        channel,
        "xhr_error_message",
        () => "Too many &lt;messages&gt; requested (maximum 5000)",
    );

    message_lists.set_current(undefined);
    message_fetch.load_messages({
        anchor: "newest",
        num_before: 0,
        num_after: 0,
        msg_list_data,
        cont: noop,
    });

    assert.equal(hide_indicators_called, true);
    assert.equal(error_message_html, "Too many &lt;messages&gt; requested (maximum 5000)");
});

run_test(
    "load_messages: 400 falls back to empty narrow when no server message",
    ({disallow, override}) => {
        const filter = new Filter([{operator: "search", operand: "zulip"}]);
        const msg_list_data = new MessageListData({
            excludes_muted_topics: false,
            filter,
        });
        const msg_list = {
            is_combined_feed_view: false,
            visibly_empty: () => true,
            data: {filter},
        };
        let hide_indicators_called = false;
        let empty_narrow_banner_shown = false;

        override(message_feed_loading, "hide_indicators", () => {
            hide_indicators_called = true;
        });
        disallow(ui_report, "generic_embed_error");
        override(narrow_banner, "show_empty_narrow_message", () => {
            empty_narrow_banner_shown = true;
        });
        override(popup_banners, "close_connection_error_popup_banner", noop);
        override(channel, "get", (opts) => {
            opts.error({
                status: 400,
                responseJSON: {},
            });
        });
        override(channel, "xhr_error_message", () => "");

        message_lists.set_current(msg_list);
        message_fetch.load_messages({
            anchor: "newest",
            num_before: 0,
            num_after: 0,
            msg_list,
            msg_list_data,
            cont: noop,
        });
        message_lists.set_current(undefined);

        assert.equal(hide_indicators_called, true);
        assert.equal(empty_narrow_banner_shown, true);
    },
);
