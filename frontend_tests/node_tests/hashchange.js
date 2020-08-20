"use strict";

set_global("$", global.make_zjquery());
const window_stub = $.create("window-stub");
set_global("location", {
    protocol: "http:",
    host: "example.com",
});
set_global("to_$", () => window_stub);

const people = zrequire("people");
zrequire("hash_util");
zrequire("hashchange");
zrequire("stream_data");
zrequire("navigate");

set_global("search", {
    update_button_visibility: () => {},
});
set_global("document", "document-stub");
set_global("history", {});

set_global("admin", {});
set_global("drafts", {});
set_global("favicon", {});
set_global("floating_recipient_bar", {});
set_global("info_overlay", {});
set_global("message_viewport", {});
set_global("narrow", {});
set_global("overlays", {});
set_global("settings", {});
set_global("subs", {});
set_global("ui_util", {});

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

function test_helper() {
    let events = [];
    let narrow_terms;

    function stub(module_name, func_name) {
        global[module_name][func_name] = () => {
            events.push(module_name + "." + func_name);
        };
    }

    stub("admin", "launch");
    stub("drafts", "launch");
    stub("floating_recipient_bar", "update");
    stub("message_viewport", "stop_auto_scrolling");
    stub("narrow", "deactivate");
    stub("overlays", "close_for_hash_change");
    stub("settings", "launch");
    stub("subs", "launch");
    stub("ui_util", "blur_active_element");

    ui_util.change_tab_to = (hash) => {
        events.push("change_tab_to " + hash);
    };

    narrow.activate = (terms) => {
        narrow_terms = terms;
        events.push("narrow.activate");
    };

    info_overlay.show = (name) => {
        events.push("info: " + name);
    };

    return {
        clear_events: () => {
            events = [];
        },
        assert_events: (expected_events) => {
            assert.deepEqual(expected_events, events);
        },
        get_narrow_terms: () => narrow_terms,
    };
}

run_test("hash_interactions", () => {
    const helper = test_helper();

    window.location.hash = "#";

    helper.clear_events();
    hashchange.initialize();
    helper.assert_events([
        "overlays.close_for_hash_change",
        "message_viewport.stop_auto_scrolling",
        "change_tab_to #message_feed_container",
        "narrow.deactivate",
        "floating_recipient_bar.update",
    ]);

    helper.clear_events();
    $(window).trigger($.Event("hashchange", {}));
    helper.assert_events([
        "overlays.close_for_hash_change",
        "message_viewport.stop_auto_scrolling",
        "change_tab_to #message_feed_container",
        "narrow.deactivate",
        "floating_recipient_bar.update",
    ]);

    window.location.hash = "#narrow/stream/Denmark";

    helper.clear_events();
    $(window).trigger($.Event("hashchange", {}));
    helper.assert_events([
        "overlays.close_for_hash_change",
        "message_viewport.stop_auto_scrolling",
        "change_tab_to #message_feed_container",
        "narrow.activate",
        "floating_recipient_bar.update",
    ]);
    let terms = helper.get_narrow_terms();
    assert.equal(terms[0].operand, "Denmark");

    window.location.hash = "#narrow";

    helper.clear_events();
    $(window).trigger($.Event("hashchange", {}));
    helper.assert_events([
        "overlays.close_for_hash_change",
        "message_viewport.stop_auto_scrolling",
        "change_tab_to #message_feed_container",
        "narrow.activate",
        "floating_recipient_bar.update",
    ]);
    terms = helper.get_narrow_terms();
    assert.equal(terms.length, 0);

    window.location.hash = "#streams/whatever";

    helper.clear_events();
    $(window).trigger($.Event("hashchange", {}));
    helper.assert_events(["overlays.close_for_hash_change", "subs.launch"]);

    window.location.hash = "#keyboard-shortcuts/whatever";

    helper.clear_events();
    $(window).trigger($.Event("hashchange", {}));
    helper.assert_events(["overlays.close_for_hash_change", "info: keyboard-shortcuts"]);

    window.location.hash = "#message-formatting/whatever";

    helper.clear_events();
    $(window).trigger($.Event("hashchange", {}));
    helper.assert_events(["overlays.close_for_hash_change", "info: message-formatting"]);

    window.location.hash = "#search-operators/whatever";

    helper.clear_events();
    $(window).trigger($.Event("hashchange", {}));
    helper.assert_events(["overlays.close_for_hash_change", "info: search-operators"]);

    window.location.hash = "#drafts";

    helper.clear_events();
    $(window).trigger($.Event("hashchange", {}));
    helper.assert_events(["overlays.close_for_hash_change", "drafts.launch"]);

    window.location.hash = "#settings/alert-words";

    helper.clear_events();
    $(window).trigger($.Event("hashchange", {}));
    helper.assert_events(["overlays.close_for_hash_change", "settings.launch"]);

    window.location.hash = "#organization/user-list-admin";

    helper.clear_events();
    $(window).trigger($.Event("hashchange", {}));
    helper.assert_events(["overlays.close_for_hash_change", "admin.launch"]);

    let called_back;

    helper.clear_events();
    hashchange.exit_overlay(() => {
        called_back = true;
    });

    helper.assert_events(["ui_util.blur_active_element"]);
    assert(called_back);
});

run_test("save_narrow", () => {
    const helper = test_helper();

    let operators = [{operator: "is", operand: "private"}];

    blueslip.expect("warn", "browser does not support pushState");
    hashchange.save_narrow(operators);

    helper.assert_events(["message_viewport.stop_auto_scrolling"]);
    assert.equal(window.location.hash, "#narrow/is/private");

    let url_pushed;
    global.history.pushState = (state, title, url) => {
        url_pushed = url;
    };

    operators = [{operator: "is", operand: "starred"}];

    helper.clear_events();
    hashchange.save_narrow(operators);
    helper.assert_events(["message_viewport.stop_auto_scrolling"]);
    assert.equal(url_pushed, "http://example.com/#narrow/is/starred");
});
