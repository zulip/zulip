"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

mock_esm("../src/resize", {
    resize_stream_filters_container() {},
});

const scheduled_messages = mock_esm("../src/scheduled_messages");

scheduled_messages.get_count = () => 555;

const left_sidebar_navigation_area = zrequire("left_sidebar_navigation_area");

run_test("update_count_in_dom", () => {
    function make_elem($elem, count_selector) {
        const $count = $(count_selector);
        $elem.set_find_results(".unread_count", $count);
        $count.set_parent($elem);

        return $elem;
    }

    const counts = {
        mentioned_message_count: 222,
        home_unread_messages: 333,
        stream_unread_messages: 666,
    };

    make_elem($(".top_left_mentions"), "<mentioned-count>");

    make_elem($(".top_left_inbox"), "<home-count>");

    make_elem($(".selected-home-view"), "<home-count>");

    make_elem($(".top_left_starred_messages"), "<starred-count>");

    make_elem($(".top_left_scheduled_messages"), "<scheduled-count>");

    make_elem($("#streams_header"), "<stream-count>");

    make_elem($("#topics_header"), "<topics-count>");

    left_sidebar_navigation_area.update_dom_with_unread_counts(counts, false);
    left_sidebar_navigation_area.update_starred_count(444);
    // Calls left_sidebar_navigation_area.update_scheduled_messages_row
    left_sidebar_navigation_area.initialize();

    assert.equal($("<mentioned-count>").text(), "222");
    assert.equal($("<home-count>").text(), "333");
    assert.equal($("<starred-count>").text(), "444");
    assert.equal($("<scheduled-count>").text(), "555");
    assert.equal($("<stream-count>").text(), "666");
    assert.equal($("<topics-count>").text(), "666");

    counts.mentioned_message_count = 0;
    scheduled_messages.get_count = () => 0;

    left_sidebar_navigation_area.update_dom_with_unread_counts(counts, false);
    left_sidebar_navigation_area.update_starred_count(0);
    left_sidebar_navigation_area.update_scheduled_messages_row();

    assert.ok(!$("<mentioned-count>").visible());
    assert.equal($("<mentioned-count>").text(), "");
    assert.equal($("<starred-count>").text(), "");
    assert.ok(!$(".top_left_scheduled_messages").visible());
});
