"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {
    clear_buddy_list,
    override_user_matches_narrow,
    buddy_list_add_user_matching_view,
    buddy_list_add_other_user,
    stub_buddy_list_elements,
} = require("./lib/buddy_list");
const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");

const padded_widget = mock_esm("../src/padded_widget");
const message_viewport = mock_esm("../src/message_viewport");

const buddy_data = zrequire("buddy_data");
const {BuddyList} = zrequire("buddy_list");
const people = zrequire("people");

function init_simulated_scrolling() {
    const elem = {
        dataset: {},
        scrollTop: 0,
        scrollHeight: 0,
    };

    $.create("#buddy_list_wrapper", {children: [elem]});

    $("#buddy_list_wrapper_padding").set_height(0);

    return elem;
}

const alice = {
    email: "alice@zulip.com",
    user_id: 10,
    full_name: "Alice Smith",
};
people.add_active_user(alice);
const bob = {
    email: "bob@zulip.com",
    user_id: 15,
    full_name: "Bob Smith",
};
people.add_active_user(bob);
const chris = {
    email: "chris@zulip.com",
    user_id: 20,
    full_name: "Chris Smith",
};
people.add_active_user(chris);
const $alice_li = $.create("alice-stub");
const $bob_li = $.create("bob-stub");

run_test("basics", ({override, mock_template}) => {
    const buddy_list = new BuddyList();
    init_simulated_scrolling();

    override(buddy_list, "items_to_html", () => "<html-stub>");
    override(message_viewport, "height", () => 550);
    override(padded_widget, "update_padding", noop);
    stub_buddy_list_elements();
    mock_template("buddy_list/view_all_users.hbs", false, () => "<view-all-users-stub>");

    let appended_to_users_matching_view;
    $("#buddy-list-users-matching-view").append = ($element) => {
        assert.equal($element.selector, "<html-stub>");
        appended_to_users_matching_view = true;
    };

    buddy_list.populate({
        all_user_ids: [alice.user_id],
    });
    assert.ok(appended_to_users_matching_view);

    const $alice_li = "alice-stub";

    override(buddy_list, "get_li_from_user_id", (opts) => {
        const user_id = opts.user_id;

        assert.equal(user_id, alice.user_id);
        return $alice_li;
    });

    const $li = buddy_list.find_li({
        key: alice.user_id,
    });
    assert.equal($li, $alice_li);
});

run_test("split list", ({override, override_rewire, mock_template}) => {
    const buddy_list = new BuddyList();
    init_simulated_scrolling();
    stub_buddy_list_elements();
    mock_template("buddy_list/view_all_users.hbs", false, () => "<view-all-users-stub>");

    override_rewire(buddy_data, "user_matches_narrow", override_user_matches_narrow);

    override(buddy_list, "items_to_html", (opts) => {
        if (opts.items.length > 0) {
            return "<html-stub>";
        }
        return "<empty-list-stub>";
    });
    override(message_viewport, "height", () => 550);
    override(padded_widget, "update_padding", noop);

    let appended_to_users_matching_view = false;
    $("#buddy-list-users-matching-view").append = ($element) => {
        if ($element.selector === "<html-stub>") {
            appended_to_users_matching_view = true;
        }
    };

    let appended_to_other_users = false;
    $("#buddy-list-other-users").append = ($element) => {
        if ($element.selector === "<html-stub>") {
            appended_to_other_users = true;
        }
    };

    // one user matching the view
    buddy_list_add_user_matching_view(alice.user_id, $alice_li);
    buddy_list.populate({
        all_user_ids: [alice.user_id],
    });
    assert.ok(appended_to_users_matching_view);
    assert.ok(!appended_to_other_users);
    appended_to_users_matching_view = false;

    // one other user
    clear_buddy_list(buddy_list);
    buddy_list_add_other_user(alice.user_id, $alice_li);
    buddy_list.populate({
        all_user_ids: [alice.user_id],
    });
    assert.ok(!appended_to_users_matching_view);
    assert.ok(appended_to_other_users);
    appended_to_other_users = false;

    // a user matching the view, and an other user
    clear_buddy_list(buddy_list);
    buddy_list_add_user_matching_view(alice.user_id, $alice_li);
    buddy_list_add_other_user(bob.user_id, $bob_li);
    buddy_list.populate({
        all_user_ids: [alice.user_id, bob.user_id],
    });
    assert.ok(appended_to_users_matching_view);
    assert.ok(appended_to_other_users);
});

run_test("find_li", ({override, mock_template}) => {
    const buddy_list = new BuddyList();

    override(buddy_list, "fill_screen_with_content", noop);
    mock_template("buddy_list/view_all_users.hbs", false, () => "<view-all-users-stub>");
    stub_buddy_list_elements();

    clear_buddy_list(buddy_list);
    buddy_list_add_user_matching_view(alice.user_id, $alice_li);
    buddy_list_add_other_user(bob.user_id, $bob_li);

    let $li = buddy_list.find_li({
        key: alice.user_id,
    });
    assert.equal($li, $alice_li);

    $li = buddy_list.find_li({
        key: bob.user_id,
    });
    assert.equal($li, $bob_li);
});

run_test("fill_screen_with_content early break on big list", ({override, mock_template}) => {
    stub_buddy_list_elements();
    const buddy_list = new BuddyList();
    const elem = init_simulated_scrolling();
    stub_buddy_list_elements();
    mock_template("buddy_list/view_all_users.hbs", false, () => "<view-all-users-stub>");

    let chunks_inserted = 0;
    override(buddy_list, "render_more", () => {
        elem.scrollHeight += 100;
        chunks_inserted += 1;
    });
    override(message_viewport, "height", () => 550);

    // We will have more than enough users, but still
    // only do 6 chunks of data (20 users per chunk)
    // because of exiting early from fill_screen_with_content
    // because of not scrolling enough to fetch more users.
    const num_users = 300;
    const user_ids = [];

    _.times(num_users, (i) => {
        const person = {
            email: "foo" + i + "@zulip.com",
            user_id: 100 + i,
            full_name: "Somebody " + i,
        };
        people.add_active_user(person);
        user_ids.push(person.user_id);
    });

    buddy_list.populate({
        all_user_ids: user_ids,
    });

    // Only 6 chunks, even though that's 120 users instead of the full 300.
    assert.equal(chunks_inserted, 6);
});

run_test("big_list", ({override, override_rewire, mock_template}) => {
    const buddy_list = new BuddyList();
    init_simulated_scrolling();

    stub_buddy_list_elements();
    override(padded_widget, "update_padding", noop);
    override(message_viewport, "height", () => 550);
    override_rewire(buddy_data, "user_matches_narrow", override_user_matches_narrow);
    mock_template("buddy_list/view_all_users.hbs", false, () => "<view-all-users-stub>");

    let items_to_html_call_count = 0;
    override(buddy_list, "items_to_html", () => {
        items_to_html_call_count += 1;
        return "<html-stub>";
    });

    const num_users = 300;
    const user_ids = [];

    // This isn't a great way of testing this, but this is here for
    // the sake of code coverage. Essentially, for a very long list,
    // these buddy list sections can collect empty messages in the middle
    // of populating (i.e. once a chunk is rendered) which later might need
    // to be removed to add users from future chunks.
    //
    // For example: chunk1 populates only users in the list of users matching,
    // the view and the empty list says "None", but chunk2 adds users to the
    // other list so the "None" message should be removed.
    //
    // Here we're just saying both lists are rendered as empty from start,
    // which doesn't actually happen, since I don't know how to properly
    // get it set in the middle of buddy_list.populate().
    $("#buddy-list-users-matching-view .empty-list-message").length = 1;
    $("#buddy-list-other-users .empty-list-message").length = 1;

    _.times(num_users, (i) => {
        const person = {
            email: "foo" + i + "@zulip.com",
            user_id: 100 + i,
            full_name: "Somebody " + i,
        };
        people.add_active_user(person);
        if (i < 100 || i % 2 === 0) {
            buddy_list_add_user_matching_view(person.user_id, $.create("stub" + i));
        } else {
            buddy_list_add_other_user(person.user_id, $.create("stub" + i));
        }
        user_ids.push(person.user_id);
    });

    buddy_list.populate({
        all_user_ids: user_ids,
    });

    // Chunks are default size 20, so there should be 300/20 = 15 chunks
    const expected_chunks_inserted = 15;
    // Two calls per chunk: one for users_matching_view and one for other_users.
    assert.equal(items_to_html_call_count, 2 * expected_chunks_inserted);
});

run_test("force_render", ({override}) => {
    const buddy_list = new BuddyList();
    buddy_list.render_count = 50;

    let num_rendered = 0;
    override(buddy_list, "render_more", (opts) => {
        num_rendered += opts.chunk_size;
    });

    buddy_list.force_render({
        pos: 60,
    });

    assert.equal(num_rendered, 60 - 50 + 3);

    // Force a contrived error case for line coverage.
    blueslip.expect("error", "cannot show user id at this position");
    buddy_list.force_render({
        pos: 10,
    });
});

run_test("find_li w/force_render", ({override}) => {
    const buddy_list = new BuddyList();

    // If we call find_li w/force_render set, and the
    // user_id is not already rendered in DOM, then the
    // widget will force-render it.
    const user_id = "999";
    const $stub_li = "stub-li";

    override(buddy_list, "get_li_from_user_id", (opts) => {
        assert.equal(opts.user_id, user_id);
        return $stub_li;
    });

    buddy_list.all_user_ids = ["foo", "bar", user_id, "baz"];

    let shown;

    override(buddy_list, "force_render", (opts) => {
        assert.equal(opts.pos, 2);
        shown = true;
    });

    const $hidden_li = buddy_list.find_li({
        key: user_id,
    });
    assert.equal($hidden_li, $stub_li);
    assert.ok(!shown);

    const $li = buddy_list.find_li({
        key: user_id,
        force_render: true,
    });

    assert.equal($li, $stub_li);
    assert.ok(shown);
});

run_test("find_li w/bad key", ({override}) => {
    const buddy_list = new BuddyList();
    override(buddy_list, "get_li_from_user_id", () => "stub-li");

    const $undefined_li = buddy_list.find_li({
        key: "not-there",
        force_render: true,
    });

    assert.deepEqual($undefined_li, undefined);
});

run_test("scrolling", ({override, mock_template}) => {
    const buddy_list = new BuddyList();
    let tried_to_fill;
    override(buddy_list, "fill_screen_with_content", () => {
        tried_to_fill = true;
    });
    mock_template("buddy_list/view_all_users.hbs", false, () => "<view-all-users-stub>");
    stub_buddy_list_elements();
    init_simulated_scrolling();
    stub_buddy_list_elements();

    clear_buddy_list(buddy_list);
    assert.ok(tried_to_fill);
    tried_to_fill = false;

    buddy_list.start_scroll_handler();
    $(buddy_list.scroll_container_selector).trigger("scroll");

    assert.ok(tried_to_fill);
});
