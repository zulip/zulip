"use strict";

set_global("$", global.make_zjquery());

zrequire("Filter", "js/filter");
zrequire("unread_ui");
const people = zrequire("people");

zrequire("top_left_corner");

run_test("narrowing", () => {
    // activating narrow

    let pm_expanded;
    let pm_closed;

    set_global("pm_list", {
        close() {
            pm_closed = true;
        },
        expand() {
            pm_expanded = true;
        },
    });

    assert(!pm_expanded);
    let filter = new Filter([{operator: "is", operand: "private"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert(pm_expanded);

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
    assert(pm_expanded);

    pm_expanded = false;
    filter = new Filter([{operator: "pm-with", operand: "bob@example.com,alice@example.com"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert(pm_expanded);

    pm_expanded = false;
    filter = new Filter([{operator: "pm-with", operand: "not@valid.com"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert(!pm_expanded);

    filter = new Filter([{operator: "is", operand: "mentioned"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert($(".top_left_mentions").hasClass("active-filter"));

    filter = new Filter([{operator: "is", operand: "starred"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert($(".top_left_starred_messages").hasClass("active-filter"));

    filter = new Filter([{operator: "in", operand: "home"}]);
    top_left_corner.handle_narrow_activated(filter);
    assert($(".top_left_all_messages").hasClass("active-filter"));

    // deactivating narrow

    pm_closed = false;
    top_left_corner.handle_narrow_deactivated();

    assert($(".top_left_all_messages").hasClass("active-filter"));
    assert(!$(".top_left_mentions").hasClass("active-filter"));
    assert(!$(".top_left_private_messages").hasClass("active-filter"));
    assert(!$(".top_left_starred_messages").hasClass("active-filter"));
    assert(pm_closed);
});

run_test("update_count_in_dom", () => {
    function make_elem(elem, count_selector, value_selector) {
        const count = $(count_selector);
        const value = $(value_selector);
        elem.set_find_results(".count", count);
        count.set_find_results(".value", value);
        count.set_parent(elem);

        return elem;
    }

    const counts = {
        mentioned_message_count: 222,
        home_unread_messages: 333,
    };

    make_elem($(".top_left_mentions"), "<mentioned-count>", "<mentioned-value>");

    make_elem($(".top_left_all_messages"), "<home-count>", "<home-value>");

    make_elem($(".top_left_starred_messages"), "<starred-count>", "<starred-value>");

    top_left_corner.update_dom_with_unread_counts(counts);
    top_left_corner.update_starred_count(444);

    assert.equal($("<mentioned-value>").text(), "222");
    assert.equal($("<home-value>").text(), "333");
    assert.equal($("<starred-value>").text(), "444");

    counts.mentioned_message_count = 0;
    top_left_corner.update_dom_with_unread_counts(counts);
    top_left_corner.update_starred_count(0);

    assert(!$("<mentioned-count>").visible());
    assert.equal($("<mentioned-value>").text(), "");
    assert.equal($("<starred-value>").text(), "");
});
