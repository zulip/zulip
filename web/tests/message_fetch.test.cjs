"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const recent_view_ui = mock_esm("../src/recent_view_ui");
const unread_ui = mock_esm("../src/unread_ui");

const {Filter} = zrequire("filter");
const {MessageListData} = zrequire("message_list_data");
const message_fetch = zrequire("message_fetch");
const {get_topic_key} = zrequire("recent_view_util");
const unread = zrequire("unread");

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

run_test("do_unread_count_updates", ({override}) => {
    unread.declare_bankruptcy();
    const stream_id = 5;
    const messages = [
        {id: 1, type: "stream", stream_id, topic: "Lunch", unread: true},
        {id: 2, type: "stream", stream_id, topic: "lunch", unread: true},
        {id: 3, type: "stream", stream_id, topic: "read", unread: false},
    ];

    let unread_counts_updated = false;
    override(unread_ui, "update_unread_counts", () => {
        unread_counts_updated = true;
    });
    let rerendered_conversation_keys;
    override(recent_view_ui, "bulk_inplace_rerender", (conversation_keys) => {
        rerendered_conversation_keys = conversation_keys;
    });

    message_fetch.do_unread_count_updates(messages);
    assert.ok(unread_counts_updated);
    assert.deepEqual(rerendered_conversation_keys, new Set([get_topic_key(stream_id, "lunch")]));

    // Fetching the same messages again discovers nothing new.
    unread_counts_updated = false;
    rerendered_conversation_keys = undefined;
    message_fetch.do_unread_count_updates(messages);
    assert.ok(!unread_counts_updated);
    assert.equal(rerendered_conversation_keys, undefined);
});
