"use strict";

const assert = require("node:assert/strict");

const {make_message_list} = require("./lib/message_list.cjs");
const {set_global, mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const fake_buddy_list = {
    scroll_container_selector: "#whatever",
    $users_matching_view_list: {
        attr() {},
    },
    $other_users_list: {
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
    set_global("setTimeout", (func) => {
        func();
    });
}

const channel = mock_esm("../src/channel");
const popovers = mock_esm("../src/popovers");
const presence = mock_esm("../src/presence");
const sidebar_ui = mock_esm("../src/sidebar_ui");

const activity_ui = zrequire("activity_ui");
const buddy_data = zrequire("buddy_data");
const message_lists = zrequire("message_lists");
const muted_users = zrequire("muted_users");
const people = zrequire("people");
const {set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");

const realm = {};
set_realm(realm);

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
        return f(opts);
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

test("clear_search with button", ({override}) => {
    override(presence, "get_status", () => "active");
    override(presence, "get_user_ids", () => all_user_ids);
    override(popovers, "hide_all", noop);
    $("#buddy-list-loading-subscribers").css = noop;

    stub_buddy_list_empty_list_message_lengths();

    // Empty because no users match this search string.
    override(fake_buddy_list, "populate", (user_ids) => {
        assert.deepEqual(user_ids, {all_user_ids: []});
    });
    set_input_val("somevalue");

    // Now we're clearing the search string and everyone shows up again.
    override(fake_buddy_list, "populate", (user_ids) => {
        assert.deepEqual(user_ids, {all_user_ids: ordered_user_ids});
    });
    $("#userlist-header-search .input-button").trigger("click");
    assert.equal($("input.user-list-filter").val(), "");
    $("#userlist-header-search .input-button").trigger("click");
});

test("clear_search", ({override}) => {
    override(realm, "realm_presence_disabled", true);
    $("#buddy-list-loading-subscribers").css = noop;

    override(popovers, "hide_all", noop);
    stub_buddy_list_empty_list_message_lengths();

    set_input_val("somevalue");
    activity_ui.clear_search();
    assert.equal($("input.user-list-filter").val(), "");
    activity_ui.clear_search();

    // We need to reset this because the unit tests aren't isolated from each other.
    set_input_val("");
});

test("fetch on search", async ({override}) => {
    override(presence, "get_user_ids", () => all_user_ids);
    override(presence, "get_status", () => "active");
    let populate_call_count = 0;
    override(fake_buddy_list, "populate", () => {
        populate_call_count += 1;
    });
    $("#buddy-list-loading-subscribers").css = noop;
    override(popovers, "hide_all", noop);
    stub_buddy_list_empty_list_message_lengths();

    const office = {stream_id: 23, name: "office", subscribed: true};
    stream_data.add_sub(office);
    message_lists.set_current(make_message_list([{operator: "stream", operand: office.stream_id}]));
    let get_call_count = 0;
    channel.get = () => {
        get_call_count += 1;
        return {
            subscribers: [1, 2, 3, 4],
        };
    };
    // Only one fetch should happen.
    set_input_val("somevalu");
    set_input_val("somevalue");
    await activity_ui.await_pending_promise_for_testing();
    assert.equal(get_call_count, 1);
    assert.equal(populate_call_count, 1);

    // Now try updating the narrow and starting a new search, before the old search
    // is resolved. We should make two requests but only only update populate the
    // buddy list for the second fetch (the first fetch returns early).
    get_call_count = 0;
    populate_call_count = 0;
    const kitchen = {stream_id: 25, name: "kitchen", subscribed: true};
    stream_data.add_sub(kitchen);
    const living_room = {stream_id: 26, name: "living_room", subscribed: true};
    stream_data.add_sub(living_room);
    message_lists.set_current(
        make_message_list([{operator: "stream", operand: kitchen.stream_id}]),
    );
    set_input_val("somevalue");
    message_lists.set_current(
        make_message_list([{operator: "stream", operand: living_room.stream_id}]),
    );
    set_input_val("somevalue");
    await activity_ui.await_pending_promise_for_testing();
    assert.equal(get_call_count, 2);
    assert.equal(populate_call_count, 1);

    // We need to reset these because the unit tests aren't isolated from each other.
    message_lists.set_current(undefined);
    activity_ui.clear_search();
    set_input_val("");
});

test("blur search right", ({override}) => {
    override(sidebar_ui, "show_userlist_sidebar", noop);
    override(popovers, "hide_all", noop);
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

test("searching", () => {
    assert.equal(activity_ui.searching(), false);
    $("input.user-list-filter").trigger("focus");
    assert.equal(activity_ui.searching(), true);
    $("input.user-list-filter").trigger("blur");
    assert.equal(activity_ui.searching(), false);
});
