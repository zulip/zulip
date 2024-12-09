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

const popovers = mock_esm("../src/popovers", {
    hide_all: noop,
});
const sidebar_ui = mock_esm("../src/sidebar_ui");

const stream_list = zrequire("stream_list");

function expand_sidebar() {
    $(".app-main .column-left").addClass("expanded");
}

function make_cursor_helper() {
    const events = [];

    stream_list.rewire_stream_cursor({
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

    function verify_collapsed() {
        assert.ok($section.hasClass("notdisplayed"));
        assert.ok(!$input.is_focused());
        assert.ok(!stream_list.searching());
        simulate_search_collapsed();
    }
    
    function toggle_and_verify(state, cursor_helper) {
        toggle_filter();
        if (state === "expanded") {
            verify_expanded();
            assert.ok(cursor_helper.events.includes("reset"));
        } else {
            verify_collapsed();
            assert.ok(cursor_helper.events.includes("clear"));
        }
    }

    toggle_and_verify("expanded", cursor_helper);

    cursor_helper.events.length = 0;
    toggle_and_verify("collapsed", cursor_helper);
});

run_test("expanding_sidebar", () => {
    $(".app-main .column-left").removeClass("expanded");

    const events = [];
    popovers.hide_all = () => {
        events.push("popovers.hide_all");
    };
    sidebar_ui.show_streamlist_sidebar = () => {
        events.push("sidebar_ui.show_streamlist_sidebar");
    };
    $("#streamlist-toggle").show();

    stream_list.initiate_search();

    assert.deepEqual(events, [
        "popovers.hide_all",
        "popovers.hide_all",
        "sidebar_ui.show_streamlist_sidebar",
    ]);
});
