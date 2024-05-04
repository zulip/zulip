"use strict";

const {strict: assert} = require("assert");

const {set_global, mock_esm, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const $ = require("./lib/zjquery");
const {realm} = require("./lib/zpage_params");

const fake_buddy_list = {
    scroll_container_selector: "#whatever",
    $users_matching_view_container: {
        attr() {},
    },
    $other_users_container: {
        attr() {},
    },
    find_li() {},
    first_key() {},
    prev_key() {},
    next_key() {},
};

mock_esm("../src/buddy_list", {
    buddy_list: fake_buddy_list,
});

function mock_setTimeout() {
    let set_timeout_function_called = false;
    set_global("setTimeout", (func) => {
        if (set_timeout_function_called) {
            // This conditional is needed to avoid indefinite calls.
            return;
        }
        set_timeout_function_called = true;
        func();
    });
}

const popovers = mock_esm("../src/popovers");
const presence = mock_esm("../src/presence");
const resize = mock_esm("../src/resize");
const sidebar_ui = mock_esm("../src/sidebar_ui");

const activity_ui = zrequire("activity_ui");
const buddy_data = zrequire("buddy_data");
const muted_users = zrequire("muted_users");
const people = zrequire("people");

const me = {
    email: "me@zulip.com",
    user_id: 999,
    full_name: "Me Myself",
};

const alice = {
    email: "alice@zulip.com",
    user_id: 1,
    full_name: "Alice Smith",
};
const fred = {
    email: "fred@zulip.com",
    user_id: 2,
    full_name: "Fred Flintstone",
};
const jill = {
    email: "jill@zulip.com",
    user_id: 3,
    full_name: "Jill Hill",
};

const all_user_ids = [alice.user_id, fred.user_id, jill.user_id, me.user_id];
const ordered_user_ids = [me.user_id, alice.user_id, fred.user_id, jill.user_id];

function test(label, f) {
    run_test(label, (opts) => {
        people.init();
        people.add_active_user(alice);
        people.add_active_user(fred);
        people.add_active_user(jill);
        people.add_active_user(me);
        people.initialize_current_user(me.user_id);
        muted_users.set_muted_users([]);
        activity_ui.set_cursor_and_filter();
        f(opts);
    });
}

function set_input_val(val) {
    $("input.user-list-filter").val(val);
    $("input.user-list-filter").trigger("input");
}

function stub_buddy_list_empty_list_message_lengths() {
    $("#buddy-list-users-matching-view .empty-list-message").length = 0;
    $("#buddy-list-other-users .empty-list-message").length = 0;
}

test("clear_search", ({override}) => {
    override(presence, "get_status", () => "active");
    override(presence, "get_user_ids", () => all_user_ids);
    override(popovers, "hide_all", noop);
    override(resize, "resize_sidebars", noop);

    stub_buddy_list_empty_list_message_lengths();

    // Empty because no users match this search string.
    override(fake_buddy_list, "populate", (user_ids) => {
        assert.deepEqual(user_ids, {all_user_ids: []});
    });
    set_input_val("somevalue");
    assert.ok(!$("#user_search_section").hasClass("notdisplayed"));

    // Now we're clearing the search string and everyone shows up again.
    override(fake_buddy_list, "populate", (user_ids) => {
        assert.deepEqual(user_ids, {all_user_ids: ordered_user_ids});
    });
    $("#clear_search_people_button").trigger("click");
    assert.equal($("input.user-list-filter").val(), "");
    $("#clear_search_people_button").trigger("click");
    assert.ok($("#user_search_section").hasClass("notdisplayed"));
});

test("escape_search", ({override}) => {
    realm.realm_presence_disabled = true;

    override(resize, "resize_sidebars", noop);
    override(popovers, "hide_all", noop);
    stub_buddy_list_empty_list_message_lengths();

    set_input_val("somevalue");
    activity_ui.escape_search();
    assert.equal($("input.user-list-filter").val(), "");
    activity_ui.escape_search();
    assert.ok($("#user_search_section").hasClass("notdisplayed"));

    // We need to reset this because the unit tests aren't isolated from each other.
    set_input_val("");
});

test("blur search right", ({override}) => {
    override(sidebar_ui, "show_userlist_sidebar", noop);
    override(popovers, "hide_all", noop);
    override(resize, "resize_sidebars", noop);
    mock_setTimeout();

    $("input.user-list-filter").closest = (selector) => {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create("right-sidebar").addClass("column-right");
    };

    $("input.user-list-filter").trigger("blur");
    assert.equal($("input.user-list-filter").is_focused(), false);
    activity_ui.initiate_search();
    assert.equal($("input.user-list-filter").is_focused(), true);
});

test("blur search left", ({override}) => {
    override(sidebar_ui, "show_streamlist_sidebar", noop);
    override(popovers, "hide_all", noop);
    override(resize, "resize_sidebars", noop);
    mock_setTimeout();

    $("input.user-list-filter").closest = (selector) => {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create("right-sidebar").addClass("column-left");
    };

    $("input.user-list-filter").trigger("blur");
    assert.equal($("input.user-list-filter").is_focused(), false);
    activity_ui.initiate_search();
    assert.equal($("input.user-list-filter").is_focused(), true);
});

test("filter_user_ids", ({override}) => {
    const user_presence = {};
    user_presence[alice.user_id] = "active";
    user_presence[fred.user_id] = "active";
    user_presence[jill.user_id] = "active";
    user_presence[me.user_id] = "active";

    override(presence, "get_status", (user_id) => user_presence[user_id]);
    override(presence, "get_user_ids", () => all_user_ids);

    function test_filter(search_text, expected_users) {
        const expected_user_ids = expected_users.map((user) => user.user_id);
        $("input.user-list-filter").val(search_text);
        const filter_text = activity_ui.get_filter_text();
        assert.deepEqual(
            buddy_data.get_filtered_and_sorted_user_ids(filter_text),
            expected_user_ids,
        );

        override(fake_buddy_list, "populate", ({all_user_ids: user_ids}) => {
            assert.deepEqual(user_ids, expected_user_ids);
        });

        activity_ui.build_user_sidebar();
    }

    // Sanity check data setup.
    assert.deepEqual(buddy_data.get_filtered_and_sorted_user_ids(), [
        me.user_id,
        alice.user_id,
        fred.user_id,
        jill.user_id,
    ]);

    // Test no match for muted users even with filter text.
    test_filter("ji", [jill]);
    muted_users.add_muted_user(jill.user_id);
    test_filter("ji", []);

    muted_users.remove_muted_user(jill.user_id);

    test_filter("abc", []); // no match
    test_filter("fred", [fred]);
    test_filter("fred,alice", [alice, fred]);
    test_filter("fr,al", [alice, fred]); // partials
    test_filter("fr|al", [alice, fred]); // | as OR-operator

    user_presence[alice.user_id] = "idle";
    test_filter("fr,al", [fred, alice]);

    user_presence[alice.user_id] = "active";
    test_filter("fr,al", [alice, fred]);
});

test("click on user header to toggle display", ({override}) => {
    const $user_filter = $("input.user-list-filter");

    override(popovers, "hide_all", noop);
    override(sidebar_ui, "show_userlist_sidebar", noop);
    override(resize, "resize_sidebars", noop);

    realm.realm_presence_disabled = true;

    assert.ok(!$("#user_search_section").hasClass("notdisplayed"));

    $user_filter.val("bla");

    $("#userlist-header").trigger("click");
    assert.ok($("#user_search_section").hasClass("notdisplayed"));
    assert.equal($user_filter.val(), "");

    $("input.user-list-filter").closest = (selector) => {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create("sidebar").addClass("column-right");
    };

    $("#userlist-header").trigger("click");
    assert.equal($("#user_search_section").hasClass("notdisplayed"), false);
});

test("searching", () => {
    assert.equal(activity_ui.searching(), false);
    $("input.user-list-filter").trigger("focus");
    assert.equal(activity_ui.searching(), true);
    $("input.user-list-filter").trigger("blur");
    assert.equal(activity_ui.searching(), false);
});
