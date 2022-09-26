"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

mock_esm("../../static/js/resize", {
    resize_stream_filters_container: () => {},
});

const {Filter} = zrequire("../js/filter");
const top_left_corner = zrequire("top_left_corner");

run_test("narrowing", () => {
    let filter = new Filter([{operator: "is", operand: "mentioned"}]);

    // activating narrow

    top_left_corner.handle_narrow_activated(filter);
    assert.ok($(".top_left_mentions").hasClass("active-filter"));

    filter = new Filter([{operator: "is", operand: "starred"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert.ok($(".top_left_starred_messages").hasClass("active-filter"));

    filter = new Filter([{operator: "in", operand: "home"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert.ok($(".top_left_all_messages").hasClass("active-filter"));

    // deactivating narrow

    top_left_corner.handle_narrow_deactivated();

    assert.ok($(".top_left_all_messages").hasClass("active-filter"));
    assert.ok(!$(".top_left_mentions").hasClass("active-filter"));
    assert.ok(!$(".top_left_starred_messages").hasClass("active-filter"));
    assert.ok(!$(".top_left_recent_topics").hasClass("active-filter"));

    set_global("setTimeout", (f) => {
        f();
    });
    top_left_corner.narrow_to_recent_topics();
    assert.ok(!$(".top_left_all_messages").hasClass("active-filter"));
    assert.ok(!$(".top_left_mentions").hasClass("active-filter"));
    assert.ok(!$(".top_left_starred_messages").hasClass("active-filter"));
    assert.ok($(".top_left_recent_topics").hasClass("active-filter"));
});

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
    };

    make_elem($(".top_left_mentions"), "<mentioned-count>");

    make_elem($(".top_left_all_messages"), "<home-count>");

    make_elem($(".top_left_starred_messages"), "<starred-count>");

    top_left_corner.update_dom_with_unread_counts(counts);
    top_left_corner.update_starred_count(444);

    assert.equal($("<mentioned-count>").text(), "222");
    assert.equal($("<home-count>").text(), "333");
    assert.equal($("<starred-count>").text(), "444");

    counts.mentioned_message_count = 0;
    top_left_corner.update_dom_with_unread_counts(counts);
    top_left_corner.update_starred_count(0);

    assert.ok(!$("<mentioned-count>").visible());
    assert.equal($("<mentioned-count>").text(), "");
    assert.equal($("<starred-count>").text(), "");
});
