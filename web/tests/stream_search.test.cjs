"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

// This tests the stream searching functionality which currently
// lives in stream_list.ts.

mock_esm("../src/resize", {
    resize_page_components: noop,

    resize_stream_filters_container: noop,
});

const popovers = mock_esm("../src/popovers");
const sidebar_ui = mock_esm("../src/sidebar_ui");

const stream_list = zrequire("stream_list");

function expand_sidebar() {
    $(".app-main .column-left").addClass("expanded");
}

function make_cursor_helper(override_rewire) {
    const events = [];

    override_rewire(stream_list, "stream_cursor", {
        reset() {
            events.push("reset");
        },
        clear() {
            events.push("clear");
        },
    });

    return {
        events,
    };
}

function clear_search_input() {
    stream_list.test_clear_search();
}

run_test("basics", ({override, override_rewire}) => {
    override(popovers, "hide_all", noop);
    override(sidebar_ui, "show_left_sidebar", noop);

    const $input = $(".stream-list-filter");

    expand_sidebar();

    let cursor_helper = make_cursor_helper(override_rewire);

    function verify_focused() {
        assert.ok(stream_list.searching());
        assert.ok($input.is_focused());
    }

    function verify_not_focused() {
        assert.ok(!stream_list.searching());
        assert.ok(!$input.is_focused());
    }

    function verify_list_updated(f) {
        let updated;
        override_rewire(stream_list, "update_streams_sidebar", () => {
            updated = true;
        });

        f();
        assert.ok(updated);
    }

    // Initiate search
    stream_list.initiate_search();
    verify_focused();

    (function add_some_text_and_clear() {
        stream_list.initiate_search();
        cursor_helper = make_cursor_helper(override_rewire);
        $input.val("foo");
        verify_list_updated(() => {
            clear_search_input();
        });
        assert.deepEqual(cursor_helper.events, ["reset"]);
    })();

    // Escape a non-empty search.
    stream_list.initiate_search();
    $input.val("foo");
    stream_list.clear_search();
    verify_not_focused();

    // Escape an empty search.
    stream_list.initiate_search();
    $input.val("");
    stream_list.clear_search();
    verify_not_focused();
});

run_test("expanding_sidebar", ({override, override_rewire}) => {
    const cursor_helper = make_cursor_helper(override_rewire);

    $(".app-main .column-left").removeClass("expanded");

    const events = [];

    override(popovers, "hide_all", () => {
        events.push("popovers.hide_all");
    });

    override(sidebar_ui, "show_left_sidebar", () => {
        events.push("popovers.hide_all", "sidebar_ui.show_streamlist_sidebar");
    });

    $("#streamlist-toggle").show();

    stream_list.initiate_search();

    assert.deepEqual(events, [
        "popovers.hide_all",
        "popovers.hide_all",
        "sidebar_ui.show_streamlist_sidebar",
    ]);

    assert.deepEqual(cursor_helper.events, ["reset"]);
});
