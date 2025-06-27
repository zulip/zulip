"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

mock_esm("../src/resize", {
    resize_stream_filters_container() {},
});

const scheduled_messages = mock_esm("../src/scheduled_messages");

scheduled_messages.get_count = () => 555;

const message_reminder = mock_esm("../src/message_reminder");
message_reminder.get_count = () => 888;

const {Filter} = zrequire("../src/filter");
const left_sidebar_navigation_area = zrequire("left_sidebar_navigation_area");

run_test("narrowing", ({override_rewire}) => {
    override_rewire(
        left_sidebar_navigation_area,
        "select_top_left_corner_item",
        (narrow_to_activate) => {
            const targets = [
                ".top_left_mentions",
                ".top_left_starred_messages",
                ".top_left_all_messages",
                ".top_left_recent_view",
                ".top_left_inbox",
            ];
            for (const target of targets) {
                $(target).removeClass("top-left-active-filter");
            }
            if (narrow_to_activate !== "") {
                $(narrow_to_activate).addClass("top-left-active-filter");
            }
        },
    );

    let filter = new Filter([{operator: "is", operand: "mentioned"}]);

    // activating narrow

    left_sidebar_navigation_area.handle_narrow_activated(filter);
    assert.ok($(".top_left_mentions").hasClass("top-left-active-filter"));

    filter = new Filter([{operator: "is", operand: "starred"}]);
    left_sidebar_navigation_area.handle_narrow_activated(filter);
    assert.ok($(".top_left_starred_messages").hasClass("top-left-active-filter"));

    filter = new Filter([{operator: "in", operand: "home"}]);
    left_sidebar_navigation_area.handle_narrow_activated(filter);
    assert.ok($(".top_left_all_messages").hasClass("top-left-active-filter"));

    // deactivating narrow

    left_sidebar_navigation_area.handle_narrow_activated(new Filter([]));

    assert.ok(!$(".top_left_all_messages").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_mentions").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_starred_messages").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_recent_view").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_inbox").hasClass("top-left-active-filter"));

    set_global("setTimeout", (f) => {
        f();
    });
    left_sidebar_navigation_area.highlight_recent_view();
    assert.ok(!$(".top_left_all_messages").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_mentions").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_starred_messages").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_inbox").hasClass("top-left-active-filter"));
    assert.ok($(".top_left_recent_view").hasClass("top-left-active-filter"));

    left_sidebar_navigation_area.handle_narrow_activated(new Filter([]));
    left_sidebar_navigation_area.highlight_inbox_view();
    assert.ok(!$(".top_left_all_messages").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_mentions").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_starred_messages").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_recent_view").hasClass("top-left-active-filter"));
    assert.ok($(".top_left_inbox").hasClass("top-left-active-filter"));

    left_sidebar_navigation_area.highlight_all_messages_view();
    assert.ok(!$(".top_left_mentions").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_starred_messages").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_recent_view").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_inbox").hasClass("top-left-active-filter"));
    assert.ok($(".top_left_all_messages").hasClass("top-left-active-filter"));
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
        stream_unread_messages: 666,
    };

    $(".selected-home-view").set_find_results(".sidebar-menu-icon", $("<menu-icon>"));

    make_elem($(".top_left_mentions"), "<mentioned-count>");

    make_elem($(".top_left_inbox"), "<home-count>");

    make_elem($(".selected-home-view"), "<home-count>");

    make_elem($(".top_left_starred_messages"), "<starred-count>");

    make_elem($(".top_left_scheduled_messages"), "<scheduled-count>");

    make_elem($(".top_left_reminders"), "<reminders-count>");

    make_elem($("#streams_header"), "<stream-count>");

    make_elem($("#topics_header"), "<topics-count>");

    left_sidebar_navigation_area.update_dom_with_unread_counts(counts, false);
    left_sidebar_navigation_area.update_starred_count(444, false);
    // Calls left_sidebar_navigation_area.update_scheduled_messages_row
    left_sidebar_navigation_area.initialize();

    assert.equal($("<mentioned-count>").text(), "222");
    assert.equal($("<home-count>").text(), "333");
    assert.equal($("<starred-count>").text(), "444");
    assert.equal($("<scheduled-count>").text(), "555");
    assert.equal($("<reminders-count>").text(), "888");
    assert.equal($("<stream-count>").text(), "666");
    assert.equal($("<topics-count>").text(), "666");

    counts.mentioned_message_count = 0;
    scheduled_messages.get_count = () => 0;
    message_reminder.get_count = () => 0;

    left_sidebar_navigation_area.update_dom_with_unread_counts(counts, false);
    left_sidebar_navigation_area.update_starred_count(444, true);
    left_sidebar_navigation_area.update_scheduled_messages_row();
    left_sidebar_navigation_area.update_reminders_row();

    assert.ok(!$("<mentioned-count>").visible());
    assert.equal($("<mentioned-count>").text(), "");
    assert.equal($("<starred-count>").text(), "444");
    assert.ok(!$(".top_left_scheduled_messages").visible());
    assert.ok(!$(".top_left_reminders").visible());
});
