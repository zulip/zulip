"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

mock_esm("../../static/js/resize", {
    resize_stream_filters_container: () => {},
});

const {Filter} = zrequire("../js/filter");
const people = zrequire("people");
const pm_list = zrequire("pm_list");
const top_left_corner = zrequire("top_left_corner");

run_test("narrowing", ({override}) => {
    // activating narrow

    let pm_expanded;
    let pm_closed;

    override(pm_list, "close", () => {
        pm_closed = true;
    });
    override(pm_list, "expand", () => {
        pm_expanded = true;
    });

    assert.ok(!pm_expanded);
    let filter = new Filter([{operator: "is", operand: "private"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert.ok(pm_expanded);

    const alice = {
        email: "alice@example.com",
        user_id: 1,
        full_name: "Alice Smith",
    };
    const bob = {
        email: "bob@example.com",
        user_id: 2,
        full_name: "Bob Patel",
    };

    people.add_active_user(alice);
    people.add_active_user(bob);

    pm_expanded = false;
    filter = new Filter([{operator: "pm-with", operand: "alice@example.com"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert.ok(pm_expanded);

    pm_expanded = false;
    filter = new Filter([{operator: "pm-with", operand: "bob@example.com,alice@example.com"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert.ok(pm_expanded);

    pm_expanded = false;
    filter = new Filter([{operator: "pm-with", operand: "not@valid.com"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert.ok(!pm_expanded);

    pm_expanded = false;
    people.deactivate(alice);
    filter = new Filter([{operator: "pm-with", operand: "alice@example.com"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert.ok(pm_expanded);

    filter = new Filter([{operator: "is", operand: "mentioned"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert.ok($(".top_left_mentions").hasClass("active-filter"));

    filter = new Filter([{operator: "is", operand: "starred"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert.ok($(".top_left_starred_messages").hasClass("active-filter"));

    filter = new Filter([{operator: "in", operand: "home"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert.ok($(".top_left_all_messages").hasClass("active-filter"));

    // deactivating narrow

    pm_closed = false;
    top_left_corner.handle_narrow_deactivated();

    assert.ok($(".top_left_all_messages").hasClass("active-filter"));
    assert.ok(!$(".top_left_mentions").hasClass("active-filter"));
    assert.ok(!$(".top_left_private_messages").hasClass("active-filter"));
    assert.ok(!$(".top_left_starred_messages").hasClass("active-filter"));
    assert.ok(!$(".top_left_recent_topics").hasClass("active-filter"));
    assert.ok(pm_closed);

    set_global("setTimeout", (f) => {
        f();
    });
    top_left_corner.narrow_to_recent_topics();
    assert.ok(!$(".top_left_all_messages").hasClass("active-filter"));
    assert.ok(!$(".top_left_mentions").hasClass("active-filter"));
    assert.ok(!$(".top_left_private_messages").hasClass("active-filter"));
    assert.ok(!$(".top_left_starred_messages").hasClass("active-filter"));
    assert.ok($(".top_left_recent_topics").hasClass("active-filter"));
});

run_test("update_count_in_dom", () => {
    function make_elem(elem, count_selector) {
        const count = $(count_selector);
        elem.set_find_results(".unread_count", count);
        count.set_parent(elem);

        return elem;
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
