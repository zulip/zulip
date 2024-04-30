"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");
const {user_settings} = require("./lib/zpage_params");

let $window_stub;
set_global("to_$", () => $window_stub);

set_global("document", "document-stub");
const history = set_global("history", {});

const admin = mock_esm("../src/admin");
const drafts_overlay_ui = mock_esm("../src/drafts_overlay_ui");
const info_overlay = mock_esm("../src/info_overlay");
const message_viewport = mock_esm("../src/message_viewport");
const overlays = mock_esm("../src/overlays");
const popovers = mock_esm("../src/popovers");
const recent_view_ui = mock_esm("../src/recent_view_ui");
const settings = mock_esm("../src/settings");
const stream_settings_ui = mock_esm("../src/stream_settings_ui");
const ui_util = mock_esm("../src/ui_util");
const ui_report = mock_esm("../src/ui_report");
set_global("favicon", {});

const browser_history = zrequire("browser_history");
const people = zrequire("people");
const hash_util = zrequire("hash_util");
const hashchange = zrequire("hashchange");
const narrow = zrequire("../src/narrow");
const stream_data = zrequire("stream_data");
const {Filter} = zrequire("../src/filter");

run_test("terms_round_trip", () => {
    let terms;
    let hash;
    let narrow;

    terms = [
        {operator: "stream", operand: "devel"},
        {operator: "topic", operand: "algol"},
    ];
    hash = hash_util.search_terms_to_hash(terms);
    assert.equal(hash, "#narrow/stream/devel/topic/algol");

    narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [
        {operator: "stream", operand: "devel", negated: false},
        {operator: "topic", operand: "algol", negated: false},
    ]);

    terms = [
        {operator: "stream", operand: "devel"},
        {operator: "topic", operand: "visual c++", negated: true},
    ];
    hash = hash_util.search_terms_to_hash(terms);
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
    terms = [{operator: "stream", operand: "Florida, USA"}];
    hash = hash_util.search_terms_to_hash(terms);
    assert.equal(hash, "#narrow/stream/987-Florida.2C-USA");
    narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [{operator: "stream", operand: "Florida, USA", negated: false}]);
});

run_test("stream_to_channel_rename", () => {
    let terms;
    let hash;
    let narrow;
    let filter;

    // Confirm the URLs generated from search terms use "stream" and "streams"
    // and that the new Filter has the new "channel" and "channels" operators.
    terms = [{operator: "channel", operand: "devel"}];
    hash = hash_util.search_terms_to_hash(terms);
    assert.equal(hash, "#narrow/stream/devel");
    narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [{operator: "stream", operand: "devel", negated: false}]);
    filter = new Filter(narrow);
    assert.deepEqual(filter.terms(), [{operator: "channel", operand: "devel", negated: false}]);

    terms = [{operator: "channels", operand: "public"}];
    hash = hash_util.search_terms_to_hash(terms);
    assert.equal(hash, "#narrow/streams/public");
    narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [{operator: "streams", operand: "public", negated: false}]);
    filter = new Filter(narrow);
    assert.deepEqual(filter.terms(), [{operator: "channels", operand: "public", negated: false}]);

    // Confirm that a narrow URL with "channel" and an enocoded stream/channel ID,
    // will be decoded correctly.
    const test_channel = {
        name: "decode",
        stream_id: 34,
    };
    stream_data.add_sub(test_channel);
    hash = "#narrow/channel/34-decode";
    narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [{operator: "channel", operand: "decode", negated: false}]);
    filter = new Filter(narrow);
    assert.deepEqual(filter.terms(), [{operator: "channel", operand: "decode", negated: false}]);
});

run_test("terms_trailing_slash", () => {
    const hash = "#narrow/stream/devel/topic/algol/";
    const narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [
        {operator: "stream", operand: "devel", negated: false},
        {operator: "topic", operand: "algol", negated: false},
    ]);
});

run_test("people_slugs", () => {
    let terms;
    let hash;
    let narrow;

    const alice = {
        email: "alice@example.com",
        user_id: 42,
        full_name: "Alice Smith",
    };

    people.add_active_user(alice);
    terms = [{operator: "sender", operand: "alice@example.com"}];
    hash = hash_util.search_terms_to_hash(terms);
    assert.equal(hash, "#narrow/sender/42-Alice-Smith");
    narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [{operator: "sender", operand: "alice@example.com", negated: false}]);

    terms = [{operator: "dm", operand: "alice@example.com"}];
    hash = hash_util.search_terms_to_hash(terms);
    assert.equal(hash, "#narrow/dm/42-Alice-Smith");
    narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [{operator: "dm", operand: "alice@example.com", negated: false}]);

    // Even though we renamed "pm-with" to "dm", preexisting
    // links/URLs with "pm-with" operator are handled correctly.
    terms = [{operator: "pm-with", operand: "alice@example.com"}];
    hash = hash_util.search_terms_to_hash(terms);
    assert.equal(hash, "#narrow/pm-with/42-Alice-Smith");
    narrow = hash_util.parse_narrow(hash.split("/"));
    assert.deepEqual(narrow, [{operator: "pm-with", operand: "alice@example.com", negated: false}]);
});

function test_helper({override, override_rewire, change_tab}) {
    let events = [];
    let narrow_terms;

    function stub(module, func_name) {
        module[func_name] = () => {
            events.push([module, func_name]);
        };
    }

    stub(admin, "launch");
    stub(admin, "build_page");
    stub(drafts_overlay_ui, "launch");
    stub(message_viewport, "stop_auto_scrolling");
    stub(overlays, "close_for_hash_change");
    stub(settings, "launch");
    stub(settings, "build_page");
    stub(stream_settings_ui, "launch");
    stub(ui_util, "blur_active_element");
    stub(ui_report, "error");

    if (change_tab) {
        override_rewire(narrow, "activate", (terms) => {
            narrow_terms = terms;
            events.push("narrow.activate");
        });

        override(info_overlay, "show", (name) => {
            events.push("info: " + name);
        });
    }

    return {
        clear_events() {
            events = [];
        },
        assert_events(expected_events) {
            assert.deepEqual(events, expected_events);
        },
        get_narrow_terms: () => narrow_terms,
    };
}

run_test("hash_interactions", ({override, override_rewire}) => {
    $window_stub = $.create("window-stub");
    user_settings.web_home_view = "recent_topics";

    const helper = test_helper({override, override_rewire, change_tab: true});

    let recent_view_ui_shown = false;
    override(recent_view_ui, "show", () => {
        recent_view_ui_shown = true;
    });
    let hide_all_called = false;
    override(popovers, "hide_all", () => {
        hide_all_called = true;
    });
    window.location.hash = "#unknown_hash";

    browser_history.clear_for_testing();
    hashchange.initialize();
    // If it's an unknown hash it should show the home view.
    assert.equal(recent_view_ui_shown, true);
    assert.equal(hide_all_called, true);
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [message_viewport, "stop_auto_scrolling"],
    ]);

    window.location.hash = "#feed";
    hide_all_called = false;

    helper.clear_events();
    $window_stub.trigger("hashchange");
    assert.equal(hide_all_called, true);
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [message_viewport, "stop_auto_scrolling"],
        "narrow.activate",
    ]);

    helper.clear_events();
    $window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [message_viewport, "stop_auto_scrolling"],
        "narrow.activate",
    ]);

    // Test old "#recent_topics" hash redirects to "#recent".
    recent_view_ui_shown = false;
    window.location.hash = "#recent_topics";

    helper.clear_events();
    $window_stub.trigger("hashchange");
    assert.equal(recent_view_ui_shown, true);
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [message_viewport, "stop_auto_scrolling"],
    ]);
    assert.equal(window.location.hash, "#recent");

    window.location.hash = "#narrow/stream/Denmark";

    helper.clear_events();
    $window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [message_viewport, "stop_auto_scrolling"],
        "narrow.activate",
    ]);
    let terms = helper.get_narrow_terms();
    assert.equal(terms[0].operand, "Denmark");

    window.location.hash = "#narrow";

    helper.clear_events();
    $window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [message_viewport, "stop_auto_scrolling"],
        "narrow.activate",
    ]);
    terms = helper.get_narrow_terms();
    assert.equal(terms.length, 0);

    // Test an invalid narrow hash
    window.location.hash = "#narrow/foo.foo";

    helper.clear_events();
    $window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [message_viewport, "stop_auto_scrolling"],
        [ui_report, "error"],
    ]);

    window.location.hash = "#channels/subscribed";

    helper.clear_events();
    $window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [stream_settings_ui, "launch"],
    ]);

    recent_view_ui_shown = false;
    window.location.hash = "#reload:send_after_reload=0...";

    helper.clear_events();
    $window_stub.trigger("hashchange");
    helper.assert_events([]);
    // If it's reload hash it shouldn't show the home view.
    assert.equal(recent_view_ui_shown, false);

    window.location.hash = "#keyboard-shortcuts/whatever";

    helper.clear_events();
    $window_stub.trigger("hashchange");
    helper.assert_events([[overlays, "close_for_hash_change"], "info: keyboard-shortcuts"]);

    window.location.hash = "#message-formatting/whatever";

    helper.clear_events();
    $window_stub.trigger("hashchange");
    helper.assert_events([[overlays, "close_for_hash_change"], "info: message-formatting"]);

    window.location.hash = "#search-operators/whatever";

    helper.clear_events();
    $window_stub.trigger("hashchange");
    helper.assert_events([[overlays, "close_for_hash_change"], "info: search-operators"]);

    window.location.hash = "#drafts";

    helper.clear_events();
    $window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [drafts_overlay_ui, "launch"],
    ]);

    window.location.hash = "#settings/alert-words";

    helper.clear_events();
    $window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [settings, "build_page"],
        [admin, "build_page"],
        [settings, "launch"],
    ]);

    window.location.hash = "#organization/user-list-admin";

    helper.clear_events();
    $window_stub.trigger("hashchange");
    helper.assert_events([
        [overlays, "close_for_hash_change"],
        [settings, "build_page"],
        [admin, "build_page"],
        [admin, "launch"],
    ]);

    helper.clear_events();
    browser_history.exit_overlay();

    helper.assert_events([[ui_util, "blur_active_element"]]);
});

run_test("save_narrow", ({override, override_rewire}) => {
    const helper = test_helper({override, override_rewire});

    let terms = [{operator: "is", operand: "dm"}];

    blueslip.expect("error", "browser does not support pushState");
    narrow.save_narrow(terms);

    helper.assert_events([[message_viewport, "stop_auto_scrolling"]]);
    assert.equal(window.location.hash, "#narrow/is/dm");

    let url_pushed;
    override(history, "pushState", (_state, _title, url) => {
        url_pushed = url;
    });

    terms = [{operator: "is", operand: "starred"}];

    helper.clear_events();
    narrow.save_narrow(terms);
    helper.assert_events([[message_viewport, "stop_auto_scrolling"]]);
    assert.equal(url_pushed, "http://zulip.zulipdev.com/#narrow/is/starred");
});
