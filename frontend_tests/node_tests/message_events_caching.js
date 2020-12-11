"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {mock_cjs, mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

mock_cjs("jquery", $);

set_global("document", "document-stub");

const noop = function () {};
window.addEventListener = noop;

const people = zrequire("people");
const {set_up, cache_fixtures} = require("./lib/events");

const {mld_cache} = zrequire("message_list_data_cache");
const {all_messages_data} = zrequire("all_messages_data");
const {MessageListView} = zrequire("../js/message_list_view");
const narrow = zrequire("narrow");
const server_events = zrequire("server_events");
const stream_data = zrequire("stream_data");
const message_list = zrequire("message_list");
const message_lists = zrequire("message_lists");
const message_helper = zrequire("message_helper");
const message_store = zrequire("message_store");

message_lists.home = new message_list.MessageList({
    muting_enabled: false,
});
message_lists.current = {
    can_mark_messages_read: () => true,
    selected_id: () => 100,
    selected_row: noop,
};
const override_MLV = {
    rerender_preserving_scrolltop: noop,
    clear_table: noop,
    get_row: () => [],
};
for (const [method, f] of Object.entries(override_MLV)) {
    MessageListView.prototype[method] = f;
}

mock_esm("../../static/js/channel", {get: noop});
mock_esm("../../static/js/compose", {update_closed_compose_buttons_for_stream: noop});
mock_esm("../../static/js/compose_actions", {on_narrow: noop});
mock_esm("../../static/js/hashchange", {save_narrow: noop});
mock_esm("../../static/js/message_scroll", {
    hide_top_of_narrow_notices: noop,
    show_loading_older: noop,
    hide_indicators: noop,
});
mock_esm("../../static/js/message_view_header", {initialize: noop});
mock_esm("../../static/js/notifications", {
    clear_compose_notifications: noop,
    redraw_title: noop,
    received_messages: noop,
});
mock_esm("../../static/js/resize", {
    resize_stream_filters_container: noop,
    resize_page_components: noop,
});
mock_esm("../../static/js/stream_list", {
    handle_narrow_activated: noop,
    update_streams_sidebar: noop,
});
mock_esm("../../static/js/ui_util", {change_tab_to: noop});
mock_esm("../../static/js/unread_ops", {
    process_visible: noop,
    process_read_messages_event: noop,
});
mock_esm("../../static/js/unread_ui", {update_unread_counts: noop});

const {alice, mark} = set_up.users;
const {denmark, usa} = set_up.streams;
const {operators_list_1, operators_list_2} = set_up.operators_list;
const {all_messages_1, all_messages_2} = set_up.all_messages;

const all_people = [alice, mark];
for (const person of all_people) {
    people.add_active_user(person);
}
const subs = [denmark, usa];
for (const sub of subs) {
    stream_data.add_sub(sub);
}

function update_message_list_all(messages) {
    all_messages_data.clear();

    for (const message of messages) {
        message_store.set_message_booleans(message);
    }
    messages.map((message) => message_helper.process_new_message(message));
    all_messages_data.add_messages(messages);
}

function generate_mld_cache(raw_operators_list) {
    mld_cache.empty();

    // This function builds the mld_cache and
    // populates each mld object's messages.
    for (const raw_operators of raw_operators_list) {
        narrow.activate(raw_operators, {});
    }
}

function verify_mld_cache(expected_mld_cache) {
    function get_ids_from_mld(key) {
        return mld_cache
            ._get_by_key(key)
            .all_messages()
            .map((msg) => msg.id);
    }

    for (const key of mld_cache.keys()) {
        const actual_msg_ids = get_ids_from_mld(key);
        assert.deepEqual(actual_msg_ids, expected_mld_cache[key]);
    }
    assert.equal(mld_cache.keys().length, _.size(expected_mld_cache));
}

server_events.home_view_loaded();

run_test("delete_messages", (override) => {
    override(narrow, "save_pre_narrow_offset_for_reload", noop);
    override(all_messages_data.fetch_status, "has_found_newest", () => true);

    update_message_list_all(all_messages_1);
    generate_mld_cache(operators_list_1);

    let expected_mld_cache = {
        "#narrow/stream/101-Denmark/topic/Copenhagen": [100],
        "#narrow/stream/101-Denmark/topic/Aarhus": [101, 102],
        "#narrow/stream/101-Denmark": [100, 101, 102],
    };
    verify_mld_cache(expected_mld_cache);

    // Delete msg={id: 101}
    let event = cache_fixtures.delete_messages_1;
    server_events._get_events_success([event]);

    expected_mld_cache = {
        "#narrow/stream/101-Denmark/topic/Copenhagen": [100],
        "#narrow/stream/101-Denmark/topic/Aarhus": [102],
        "#narrow/stream/101-Denmark": [100, 102],
    };
    verify_mld_cache(expected_mld_cache);

    // Delete msg={id: 102}
    event = cache_fixtures.delete_messages_2;
    server_events._get_events_success([event]);

    // Topic Aarhus gets deleted from MLDCache as it is now empty.
    expected_mld_cache = {
        "#narrow/stream/101-Denmark/topic/Copenhagen": [100],
        "#narrow/stream/101-Denmark": [100],
    };
    verify_mld_cache(expected_mld_cache);
});

run_test("add_messages", (override) => {
    override(narrow, "save_pre_narrow_offset_for_reload", noop);
    override(all_messages_data.fetch_status, "has_found_newest", () => true);

    update_message_list_all(all_messages_1);
    generate_mld_cache(operators_list_1);

    let expected_mld_cache = {
        "#narrow/stream/101-Denmark/topic/Copenhagen": [100],
        "#narrow/stream/101-Denmark/topic/Aarhus": [101, 102],
        "#narrow/stream/101-Denmark": [100, 101, 102],
    };
    verify_mld_cache(expected_mld_cache);

    // Insert new msg={id: 103, topic: Copenhagen}
    const event = cache_fixtures.add_messages;
    server_events._get_events_success([event]);

    expected_mld_cache = {
        "#narrow/stream/101-Denmark/topic/Copenhagen": [100, 103],
        "#narrow/stream/101-Denmark/topic/Aarhus": [101, 102],
        "#narrow/stream/101-Denmark": [100, 101, 102, 103],
    };
    verify_mld_cache(expected_mld_cache);
});

run_test("update_messages", (override) => {
    override(narrow, "save_pre_narrow_offset_for_reload", noop);
    override(all_messages_data.fetch_status, "has_found_newest", () => true);

    update_message_list_all(all_messages_2);
    generate_mld_cache(operators_list_2);

    let expected_mld_cache = {
        "#narrow/stream/101-Denmark/topic/Copenhagen": [100],
        "#narrow/stream/101-Denmark/topic/Aarhus": [101, 102],
        "#narrow/stream/101-Denmark": [100, 101, 102],
        "#narrow/stream/201-USA/topic/California": [202],
        "#narrow/stream/201-USA/topic/Florida": [200, 201],
        "#narrow/stream/201-USA": [200, 201, 202],
    };
    verify_mld_cache(expected_mld_cache);

    // Update content of msg={id: 103}
    let event = cache_fixtures.update_message_1;
    assert.equal(message_store.get(event.message_id).content, event.orig_content);
    server_events._get_events_success([event]);

    verify_mld_cache(expected_mld_cache);
    assert.equal(message_store.get(event.message_id).raw_content, event.content);

    // Rename topic Aarhus to Copenhagen
    event = cache_fixtures.update_message_2;
    server_events._get_events_success([event]);

    expected_mld_cache = {
        "#narrow/stream/101-Denmark/topic/Copenhagen": [100, 101, 102],
        "#narrow/stream/101-Denmark": [100, 101, 102],
        "#narrow/stream/201-USA/topic/California": [202],
        "#narrow/stream/201-USA/topic/Florida": [200, 201],
        "#narrow/stream/201-USA": [200, 201, 202],
    };
    verify_mld_cache(expected_mld_cache);

    // Move all messages in from USA/Florida to Denmark/Copenhagen
    event = cache_fixtures.update_message_3;
    server_events._get_events_success([event]);

    expected_mld_cache = {
        "#narrow/stream/101-Denmark/topic/Copenhagen": [100, 101, 102, 200, 201],
        "#narrow/stream/101-Denmark": [100, 101, 102, 200, 201],
        "#narrow/stream/201-USA/topic/California": [202],
        "#narrow/stream/201-USA": [202],
    };
    verify_mld_cache(expected_mld_cache);
});
