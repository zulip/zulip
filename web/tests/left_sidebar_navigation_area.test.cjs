"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

mock_esm("../src/resize", {
    resize_stream_filters_container() {},
});

const {Filter} = zrequire("../src/filter");
const left_sidebar_navigation_area = zrequire("left_sidebar_navigation_area");
const message_store = zrequire("message_store");
const reactions = zrequire("reactions");
const people = zrequire("people");
const scheduled_messages = zrequire("scheduled_messages");
const message_reminder = zrequire("message_reminder");

const me = {user_id: 1, email: "me@example.com", full_name: "Me Myself"};
people.add_active_user(me);
people.initialize_current_user(me.user_id);

function cache_my_message(message_id) {
    // A new reaction counts only while its message is cached.
    message_store.update_message_cache({
        message: {id: message_id, type: "private", sender_id: me.user_id, topic_links: []},
    });
}

function my_reaction_event(message_id, user_id) {
    return {
        message_id,
        message_sender_id: me.user_id,
        user_id,
        reaction_type: "unicode_emoji",
        emoji_name: "tada",
        emoji_code: "1f389",
    };
}

run_test("narrowing", ({override_rewire}) => {
    override_rewire(
        left_sidebar_navigation_area,
        "select_top_left_corner_item",
        (narrow_to_activate) => {
            const targets = [
                ".top_left_mentions",
                ".top_left_my_reactions",
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

    // Opening the reactions view is how the client learns that the user has
    // looked at the new reactions it was counting, so it clears the count.
    $(".top_left_my_reactions").set_find_results(".unread_count", $("<my-reactions-narrow-count>"));
    cache_my_message(1);
    reactions.increment_new_reaction_count(my_reaction_event(1, 2));
    assert.equal(reactions.get_count(), 1);
    filter = new Filter([
        {operator: "sender", operand: me.user_id},
        {operator: "has", operand: "reaction"},
    ]);
    left_sidebar_navigation_area.handle_narrow_activated(filter);
    assert.ok($(".top_left_my_reactions").hasClass("top-left-active-filter"));
    assert.equal(reactions.get_count(), 0);
    assert.equal($("<my-reactions-narrow-count>").text(), "");

    // A reaction that arrives while the reactions view is open counts until
    // the user leaves the view, which clears it too. A reactions view for
    // someone else's messages is a different narrow, so going there leaves
    // the view.
    const my_reactions_filter = filter;
    reactions.increment_new_reaction_count(my_reaction_event(1, 2));
    assert.equal(reactions.get_count(), 1);
    filter = new Filter([
        {operator: "sender", operand: 2},
        {operator: "has", operand: "reaction"},
    ]);
    left_sidebar_navigation_area.handle_narrow_activated(filter);
    assert.ok(!$(".top_left_my_reactions").hasClass("top-left-active-filter"));
    assert.equal(reactions.get_count(), 0);

    // Moving between other views leaves the count alone.
    reactions.increment_new_reaction_count(my_reaction_event(1, 2));
    left_sidebar_navigation_area.handle_narrow_activated(filter);
    left_sidebar_navigation_area.handle_narrow_activated(
        new Filter([{operator: "is", operand: "starred"}]),
    );
    assert.equal(reactions.get_count(), 1);

    // Leaving the reactions view for Inbox or Recent conversations, which
    // are not narrows, clears the count as well.
    set_global("setTimeout", (f) => {
        f();
    });
    left_sidebar_navigation_area.handle_narrow_activated(my_reactions_filter);
    reactions.increment_new_reaction_count(my_reaction_event(1, 2));
    left_sidebar_navigation_area.highlight_inbox_view();
    assert.equal(reactions.get_count(), 0);

    left_sidebar_navigation_area.handle_narrow_activated(my_reactions_filter);
    reactions.increment_new_reaction_count(my_reaction_event(1, 2));
    left_sidebar_navigation_area.highlight_recent_view();
    assert.equal(reactions.get_count(), 0);

    // deactivating narrow

    left_sidebar_navigation_area.handle_narrow_activated(new Filter([]));

    assert.ok(!$(".top_left_all_messages").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_mentions").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_starred_messages").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_recent_view").hasClass("top-left-active-filter"));
    assert.ok(!$(".top_left_inbox").hasClass("top-left-active-filter"));

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
        stream_count: new Map(),
    };
    message_reminder.set_reminders_by_id_for_testing(new Map([[1, {id: 1}]]));
    scheduled_messages.set_scheduled_messages_by_id_for_testing(
        new Map([
            [1, {id: 1}],
            [2, {id: 2}],
        ]),
    );

    $(".selected-home-view").set_find_results(".sidebar-menu-icon", $("<menu-icon>"));

    make_elem($(".top_left_mentions"), "<mentioned-count>");

    make_elem($(".top_left_inbox"), "<home-count>");

    make_elem($(".selected-home-view"), "<home-count>");

    make_elem($(".top_left_condensed_unread_marker"), "<condensed-unread-count>");

    make_elem($(".top_left_starred_messages"), "<starred-count>");

    make_elem($(".top_left_scheduled_messages"), "<scheduled-count>");

    make_elem($(".top_left_reminders"), "<reminders-count>");

    make_elem($(".top_left_my_reactions"), "<my-reactions-count>");

    cache_my_message(10);
    reactions.increment_new_reaction_count(my_reaction_event(10, 2));
    reactions.increment_new_reaction_count(my_reaction_event(10, 3));

    left_sidebar_navigation_area.update_dom_with_unread_counts(counts, false);
    left_sidebar_navigation_area.update_starred_count(444, false);
    left_sidebar_navigation_area.update_scheduled_messages_row();
    left_sidebar_navigation_area.update_reminders_row();
    left_sidebar_navigation_area.update_my_reactions_row();

    assert.equal($("<mentioned-count>").text(), "222");
    assert.equal($("<home-count>").text(), "333");
    assert.equal($("<condensed-unread-count>").text(), "333");
    assert.equal($("<starred-count>").text(), "444");
    assert.equal($("<scheduled-count>").text(), "2");
    assert.equal($("<reminders-count>").text(), "1");
    assert.equal($("<my-reactions-count>").text(), "2");
    assert.ok(!$(".top_left_scheduled_messages").hasClass("hidden-by-filters"));
    assert.ok(!$(".top_left_reminders").hasClass("hidden-by-filters"));
    assert.ok($(".top_left_my_reactions").hasClass("new-unread"));

    counts.mentioned_message_count = 0;
    reactions.clear();
    message_reminder.set_reminders_by_id_for_testing(new Map());
    scheduled_messages.set_scheduled_messages_by_id_for_testing(new Map());

    left_sidebar_navigation_area.update_dom_with_unread_counts(counts, false);
    // Starred count is hidden.
    left_sidebar_navigation_area.update_starred_count(444, true);
    left_sidebar_navigation_area.update_scheduled_messages_row();
    left_sidebar_navigation_area.update_reminders_row();
    left_sidebar_navigation_area.update_my_reactions_row();

    assert.ok(!$("<mentioned-count>").visible());
    assert.equal($("<mentioned-count>").text(), "");
    assert.equal($("<starred-count>").text(), "444");
    assert.ok($(".top_left_starred_messages").hasClass("hide_starred_message_count"));
    assert.ok($(".top_left_scheduled_messages").hasClass("hidden-by-filters"));
    assert.ok($(".top_left_reminders").hasClass("hidden-by-filters"));
    assert.ok(!$("<my-reactions-count>").visible());
    assert.equal($("<my-reactions-count>").text(), "");
});
