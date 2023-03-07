"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

// This tests the stream searching functionality which currently
// lives in stream_list.js.

const noop = () => {};

mock_esm("../src/resize", {
    resize_page_components: noop,

    resize_stream_filters_container: noop,
});

const popovers = mock_esm("../src/popovers");
const stream_popover = mock_esm("../src/stream_popover");

const stream_list = zrequire("stream_list");

function expand_sidebar() {
    $(".app-main .column-left").addClass("expanded");
}

function make_cursor_helper() {
    const events = [];

    stream_list.__Rewire__("stream_cursor", {
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

function simulate_search_expanded() {
    // The way we check if the search widget is expanded
    // is kind of awkward.

    $(".stream_search_section.notdisplayed").length = 0;
}

function simulate_search_collapsed() {
    $(".stream_search_section.notdisplayed").length = 1;
}

function toggle_filter() {
    stream_list.toggle_filter_displayed({preventDefault: noop});
}

function clear_search_input() {
    stream_list.clear_search({stopPropagation: noop});
}

run_test("basics", ({override_rewire}) => {
    let cursor_helper;
    const $input = $(".stream-list-filter");
    const $section = $(".stream_search_section");

    expand_sidebar();
    $section.addClass("notdisplayed");

    cursor_helper = make_cursor_helper();

    function verify_expanded() {
        assert.ok(!$section.hasClass("notdisplayed"));
        simulate_search_expanded();
    }

    function verify_focused() {
        assert.ok(stream_list.searching());
        assert.ok($input.is_focused());
    }

    function verify_blurred() {
        assert.ok(stream_list.searching());
        assert.ok($input.is_focused());
    }

    function verify_collapsed() {
        assert.ok($section.hasClass("notdisplayed"));
        assert.ok(!$input.is_focused());
        assert.ok(!stream_list.searching());
        simulate_search_collapsed();
    }

    function verify_list_updated(f) {
        let updated;
        override_rewire(stream_list, "update_streams_sidebar", () => {
            updated = true;
        });

        f();
        assert.ok(updated);
    }

    // Initiate search (so expand widget).
    stream_list.initiate_search();
    verify_expanded();
    verify_focused();

    assert.deepEqual(cursor_helper.events, ["reset"]);

    // Collapse the widget.
    cursor_helper = make_cursor_helper();

    toggle_filter();
    verify_collapsed();

    assert.deepEqual(cursor_helper.events, ["clear"]);

    // Expand the widget.
    toggle_filter();
    verify_expanded();
    verify_focused();

    (function add_some_text_and_collapse() {
        cursor_helper = make_cursor_helper();
        $input.val("foo");
        verify_list_updated(() => {
            toggle_filter();
        });

        verify_collapsed();
        assert.deepEqual(cursor_helper.events, ["reset", "clear"]);
    })();

    // Expand the widget.
    toggle_filter();
    verify_expanded();
    verify_focused();

    // Clear an empty search.
    clear_search_input();
    verify_collapsed();

    // Expand the widget.
    toggle_filter();
    stream_list.initiate_search();

    // Clear a non-empty search.
    $input.val("foo");
    verify_list_updated(() => {
        clear_search_input();
    });
    verify_expanded();

    // Expand the widget.
    toggle_filter();
    stream_list.initiate_search();

    // Escape a non-empty search.
    $input.val("foo");
    stream_list.escape_search();
    verify_blurred();

    // Expand the widget.
    toggle_filter();
    stream_list.initiate_search();

    // Escape an empty search.
    $input.val("");
    stream_list.escape_search();
    verify_collapsed();
});

run_test("expanding_sidebar", () => {
    $(".app-main .column-left").removeClass("expanded");

    const events = [];
    popovers.hide_all = () => {
        events.push("popovers.hide_all");
    };
    stream_popover.show_streamlist_sidebar = () => {
        events.push("stream_popover.show_streamlist_sidebar");
    };
    $("#streamlist-toggle").show();

    stream_list.initiate_search();

    assert.deepEqual(events, ["popovers.hide_all", "stream_popover.show_streamlist_sidebar"]);
});
