"use strict";

const assert = require("node:assert/strict");

const {make_user} = require("./lib/example_user.cjs");
const {clock, mock_esm, zrequire} = require("./lib/namespace.cjs");
const {noop, run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const channel = mock_esm("../src/channel");
const emoji_frequency = mock_esm("../src/emoji_frequency");
const navbar_alerts = mock_esm("../src/navbar_alerts");
mock_esm("../src/popup_banners", {
    close_connection_error_popup_banner: noop,
});
const recent_view_ui = mock_esm("../src/recent_view_ui", {
    hide_loading_indicator: noop,
    process_messages: noop,
    show_loading_indicator: noop,
});
const unread_ui = mock_esm("../src/unread_ui");

const {Filter} = zrequire("filter");
const {MessageListData} = zrequire("message_list_data");
const message_fetch = zrequire("message_fetch");
const people = zrequire("people");
const {recent_view_messages_data} = zrequire("recent_view_messages_data");
const {get_topic_key} = zrequire("recent_view_util");
const unread = zrequire("unread");
const {initialize_user_settings} = zrequire("user_settings");

initialize_user_settings({user_settings: {}});

const iago = make_user({
    email: "iago@zulip.com",
    user_id: 5,
    full_name: "Iago",
});
people.add_active_user(iago);

function make_raw_stream_message(id) {
    return {
        avatar_url: null,
        client: "website",
        content: "<p>Hello</p>",
        content_type: "text/html",
        display_recipient: "Verona",
        flags: ["read"],
        id,
        is_me_message: false,
        reactions: [],
        sender_email: iago.email,
        sender_full_name: iago.full_name,
        sender_id: iago.user_id,
        stream_id: 1,
        subject: "Lunch",
        submessages: [],
        timestamp: 1700000000 + id,
        topic_links: [],
        type: "stream",
    };
}

// Calls message_fetch.initialize() and answers its first request for
// Recent conversations with a batch that doesn't reach the oldest
// message. Returns the list that records every channel.get request,
// including ones made later.
function initialize_with_older_history_remaining(override) {
    const requests = [];
    override(channel, "get", (request) => {
        requests.push(request);
    });

    message_fetch.initialize(noop);

    assert.equal(requests.length, 1);
    assert.equal(requests[0].url, "/json/messages");
    assert.equal(requests[0].data.anchor, "newest");
    assert.equal(requests[0].data.num_before, 1000);
    requests[0].success({
        // LARGER_THAN_MAX_MESSAGE_ID, which the server returns as the
        // anchor for "newest".
        anchor: 10000000000000000,
        found_anchor: false,
        found_newest: true,
        found_oldest: false,
        history_limited: false,
        messages: [make_raw_stream_message(101), make_raw_stream_message(102)],
        msg: "",
        result: "success",
    });
    return requests;
}

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

run_test("initialize backfills older history for logged-in users", ({disallow, override}) => {
    page_params.is_spectator = false;
    // The post-backfill hooks only run once backfilling is done.
    disallow(emoji_frequency, "initialize_frequently_used_emojis");
    disallow(navbar_alerts, "check_and_show_muted_messages_banner");

    const requests = initialize_with_older_history_remaining(override);

    // The next batch is requested after a delay, starting from the
    // oldest message we have.
    assert.equal(requests.length, 1);
    clock.runAll();
    assert.equal(requests.length, 2);
    assert.equal(requests[1].data.anchor, "101");
    assert.equal(requests[1].data.num_before, 2000);
    assert.equal(requests[1].data.num_after, 0);
});

run_test("initialize doesn't backfill older history for spectators", ({override}) => {
    page_params.is_spectator = true;
    let initialized_frequently_used_emojis = false;
    override(emoji_frequency, "initialize_frequently_used_emojis", () => {
        initialized_frequently_used_emojis = true;
    });
    let checked_muted_messages_banner = false;
    override(navbar_alerts, "check_and_show_muted_messages_banner", () => {
        checked_muted_messages_banner = true;
    });

    const requests = initialize_with_older_history_remaining(override);

    clock.runAll();
    assert.equal(requests.length, 1);
    assert.ok(initialized_frequently_used_emojis);
    assert.ok(checked_muted_messages_banner);
    // "Load more" in Recent conversations can still fetch older history.
    assert.ok(recent_view_messages_data.fetch_status.can_load_older_messages());
});
