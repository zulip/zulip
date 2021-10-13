"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const $ = require("../zjsunit/zjquery");
const {user_settings} = require("../zjsunit/zpage_params");

let window_stub;
set_global("to_$", () => window_stub);

mock_esm("../../static/js/search", {
    update_button_visibility: () => {},
});
set_global("document", "document-stub");
const history = set_global("history", {});

const admin = mock_esm("../../static/js/admin");
const drafts = mock_esm("../../static/js/drafts");
const floating_recipient_bar = mock_esm("../../static/js/floating_recipient_bar");
const info_overlay = mock_esm("../../static/js/info_overlay");
const message_viewport = mock_esm("../../static/js/message_viewport");
const narrow = zrequire("../../static/js/narrow");
const overlays = mock_esm("../../static/js/overlays");
const settings = mock_esm("../../static/js/settings");
const stream_settings_ui = mock_esm("../../static/js/stream_settings_ui");
const ui_util = mock_esm("../../static/js/ui_util");
mock_esm("../../static/js/top_left_corner", {
    handle_narrow_deactivated: () => {},
});
set_global("favicon", {});

const browser_history = zrequire("browser_history");
const people = zrequire("people");
const hash_util = zrequire("hash_util");
const hashchange = zrequire("hashchange");
const stream_data = zrequire("stream_data");

const recent_topics_util = zrequire("recent_topics_util");
const recent_topics_ui = zrequire("recent_topics_ui");

run_test("operators_round_trip", () => {
    let operators;
    let hash;
    let narrow;

    operators = [
        {operator: "stream", operand: "devel"},
        {operator: "topic", operand: "algol"},
    ];
    hash = hash_util.operators_to_hash(operators);
    assert.equal(hash, "#narrow/stream/devel/topic/algol");

    narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [
        {operator: "stream", operand: "devel", negated: false},
        {operator: "topic", operand: "algol", negated: false},
    ]);

    operators = [
        {operator: "stream", operand: "devel"},
        {operator: "topic", operand: "visual c++", negated: true},
    ];
    hash = hash_util.operators_to_hash(operators);
    assert.equal(hash, "#narrow/stream/devel/-topic/visual.20c.2B.2B");

    narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [
        {operator: "stream", operand: "devel", negated: false},
        {operator: "topic", operand: "visual c++", negated: true},
    ]);

    // test new encodings, where we have a stream id
    const florida_stream = {
        name: "Florida, USA",
        stream_id: 987,
    };
    stream_data.add_sub(florida_stream);
    operators = [{operator: "stream", operand: "Florida, USA"}];
    hash = hash_util.operators_to_hash(operators);
    assert.equal(hash, "#narrow/stream/987-Florida.2C-USA");
    narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [{operator: "stream", operand: "Florida, USA", negated: false}]);
});

run_test("operators_trailing_slash", () => {
    const hash = "#narrow/stream/devel/topic/algol/";
    const narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [
        {operator: "stream", operand: "devel", negated: false},
        {operator: "topic", operand: "algol", negated: false},
    ]);
});

run_test("people_slugs", () => {
    let operators;
    let hash;

    const alice = {
        email: "alice@example.com",
        user_id: 42,
        full_name: "Alice Smith",
    };

    people.add_active_user(alice);
    operators = [{operator: "sender", operand: "alice@example.com"}];
    hash = hash_util.operators_to_hash(operators);
    assert.equal(hash, "#narrow/sender/42-alice");
    const narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [{operator: "sender", operand: "alice@example.com", negated: false}]);

    operators = [{operator: "pm-with", operand: "alice@example.com"}];
    hash = hash_util.operators_to_hash(operators);
    assert.equal(hash, "#narrow/pm-with/42-alice");
});

function test_helper({override, change_tab}) {
    let events = [];
    let narrow_terms;

    function stub(module, func_name) {
        module[func_name] = () => {
            events.push([module, func_name]);
        };
    }

    stub(admin, "launch");
    stub(drafts, "launch");
    stub(floating_recipient_bar, "update");
    stub(message_viewport, "stop_auto_scrolling");
    stub(narrow, "deactivate");
    stub(overlays, "close_for_hash_change");
    stub(settings, "launch");
    stub(stream_settings_ui, "launch");
    stub(ui_util, "blur_active_element");

    if (change_tab) {
        override(ui_util, "change_tab_to", (hash) => {
            events.push("change_tab_to " + hash);
        });

        override(narrow, "activate", (terms) => {
            narrow_terms = terms;
            events.push("narrow.activate");
        });

        override(info_overlay, "show", (name) => {
            events.push("info: " + name);
        });
    }

    return {
        clear_events: () => {
            events = [];
        },
        assert_events: (expected_events) => {
            assert.deepEqual(events, expected_events);
        },
        get_narrow_terms: () => narrow_terms,
    };
}

run_test("hash_interactions", ({override}) => {
    window_stub = $.create("window-stub");
    user_settings.default_view = "recent_topics";

    override(recent_topics_util, "is_visible", () => false);
    const helper = test_helper({override, change_tab: true});

    let recent_topics_ui_shown = false;
    override(recent_topics_ui, "show", () => {
        recent_topics_ui_shown = true;
    });
    window.location.hash = "#unknown_hash";

    browser_history.clear_for_testing();
    hashchange.initialize();
    // If it's an unknown hash it should show the default view.
    assert.equal(recent_topics_ui_shown, true);
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [message_viewport, "stop_auto_scrolling"],
    ]);

    window.location.hash = "#all_messages";

    helper.clear_events();
    window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [message_viewport, "stop_auto_scrolling"],
        "change_tab_to #message_feed_container",
        [narrow, "deactivate"],
        [floating_recipient_bar, "update"],
    ]);

    helper.clear_events();
    window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [message_viewport, "stop_auto_scrolling"],
        "change_tab_to #message_feed_container",
        [narrow, "deactivate"],
        [floating_recipient_bar, "update"],
    ]);

    window.location.hash = "#narrow/stream/Denmark";

    helper.clear_events();
    window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [message_viewport, "stop_auto_scrolling"],
        "change_tab_to #message_feed_container",
        "narrow.activate",
        [floating_recipient_bar, "update"],
    ]);
    let terms = helper.get_narrow_terms();
    assert.equal(terms[0].operand, "Denmark");

    window.location.hash = "#narrow";

    helper.clear_events();
    window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [message_viewport, "stop_auto_scrolling"],
        "change_tab_to #message_feed_container",
        "narrow.activate",
        [floating_recipient_bar, "update"],
    ]);
    terms = helper.get_narrow_terms();
    assert.equal(terms.length, 0);

    window.location.hash = "#streams/whatever";

    helper.clear_events();
    window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [stream_settings_ui, "launch"],
    ]);

    recent_topics_ui_shown = false;
    window.location.hash = "#reload:send_after_reload=0...";

    helper.clear_events();
    window_stub.trigger("hashchange");
    helper.assert_events([]);
    // If it's reload hash it shouldn't show the default view.
    assert.equal(recent_topics_ui_shown, false);

    window.location.hash = "#keyboard-shortcuts/whatever";

    helper.clear_events();
    window_stub.trigger("hashchange");
    helper.assert_events([[overlays, "close_for_hash_change"], "info: keyboard-shortcuts"]);

    window.location.hash = "#message-formatting/whatever";

    helper.clear_events();
    window_stub.trigger("hashchange");
    helper.assert_events([[overlays, "close_for_hash_change"], "info: message-formatting"]);

    window.location.hash = "#search-operators/whatever";

    helper.clear_events();
    window_stub.trigger("hashchange");
    helper.assert_events([[overlays, "close_for_hash_change"], "info: search-operators"]);

    window.location.hash = "#drafts";

    helper.clear_events();
    window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [drafts, "launch"],
    ]);

    window.location.hash = "#settings/alert-words";

    helper.clear_events();
    window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [settings, "launch"],
    ]);

    window.location.hash = "#organization/user-list-admin";

    helper.clear_events();
    window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [admin, "launch"],
    ]);

    helper.clear_events();
    browser_history.exit_overlay();

    helper.assert_events([[ui_util, "blur_active_element"]]);
});

run_test("save_narrow", ({override}) => {
    override(recent_topics_util, "is_visible", () => false);

    const helper = test_helper({override});

    let operators = [{operator: "is", operand: "private"}];

    blueslip.expect("warn", "browser does not support pushState");
    hashchange.save_narrow(operators);

    helper.assert_events([[message_viewport, "stop_auto_scrolling"]]);
    assert.equal(window.location.hash, "#narrow/is/private");

    let url_pushed;
    override(history, "pushState", (state, title, url) => {
        url_pushed = url;
    });

    operators = [{operator: "is", operand: "starred"}];

    helper.clear_events();
    hashchange.save_narrow(operators);
    helper.assert_events([[message_viewport, "stop_auto_scrolling"]]);
    assert.equal(url_pushed, "http://zulip.zulipdev.com/#narrow/is/starred");
});
