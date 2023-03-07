"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params} = require("./lib/zpage_params");

const _document = {
    hasFocus() {
        return true;
    },
};

const fake_buddy_list = {
    scroll_container_sel: "#whatever",
    find_li() {},
    first_key() {},
    prev_key() {},
    next_key() {},
};

mock_esm("../src/buddy_list", {
    buddy_list: fake_buddy_list,
});

const popovers = mock_esm("../src/popovers");
const presence = mock_esm("../src/presence");
const stream_popover = mock_esm("../src/stream_popover");
const resize = mock_esm("../src/resize");

set_global("document", _document);

const activity = zrequire("activity");
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
    run_test(label, ({override}) => {
        people.init();
        people.add_active_user(alice);
        people.add_active_user(fred);
        people.add_active_user(jill);
        people.add_active_user(me);
        people.initialize_current_user(me.user_id);
        muted_users.set_muted_users([]);
        activity.set_cursor_and_filter();
        f({override});
    });
}

test("clear_search", ({override}) => {
    override(fake_buddy_list, "populate", (user_ids) => {
        assert.deepEqual(user_ids, {keys: ordered_user_ids});
    });
    override(presence, "get_status", () => "active");
    override(presence, "get_user_ids", () => all_user_ids);
    override(resize, "resize_sidebars", () => {});

    $(".user-list-filter").val("somevalue");
    assert.ok(!$("#user_search_section").hasClass("notdisplayed"));
    $("#clear_search_people_button").trigger("click");
    assert.equal($(".user-list-filter").val(), "");
    $("#clear_search_people_button").trigger("click");
    assert.ok($("#user_search_section").hasClass("notdisplayed"));
});

test("escape_search", ({override}) => {
    page_params.realm_presence_disabled = true;

    override(resize, "resize_sidebars", () => {});
    override(popovers, "hide_all_except_sidebars", () => {});

    $(".user-list-filter").val("somevalue");
    activity.escape_search();
    assert.equal($(".user-list-filter").val(), "");
    activity.escape_search();
    assert.ok($("#user_search_section").hasClass("notdisplayed"));
});

test("blur search right", ({override}) => {
    override(popovers, "show_userlist_sidebar", () => {});
    override(popovers, "hide_all", () => {});
    override(popovers, "hide_all_except_sidebars", () => {});
    override(resize, "resize_sidebars", () => {});

    $(".user-list-filter").closest = (selector) => {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create("right-sidebar").addClass("column-right");
    };

    $(".user-list-filter").trigger("blur");
    assert.equal($(".user-list-filter").is_focused(), false);
    activity.initiate_search();
    assert.equal($(".user-list-filter").is_focused(), true);
});

test("blur search left", ({override}) => {
    override(stream_popover, "show_streamlist_sidebar", () => {});
    override(popovers, "hide_all", () => {});
    override(popovers, "hide_all_except_sidebars", () => {});
    override(resize, "resize_sidebars", () => {});

    $(".user-list-filter").closest = (selector) => {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create("right-sidebar").addClass("column-left");
    };

    $(".user-list-filter").trigger("blur");
    assert.equal($(".user-list-filter").is_focused(), false);
    activity.initiate_search();
    assert.equal($(".user-list-filter").is_focused(), true);
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
        $(".user-list-filter").val(search_text);
        const filter_text = activity.get_filter_text();
        assert.deepEqual(
            buddy_data.get_filtered_and_sorted_user_ids(filter_text),
            expected_user_ids,
        );

        override(fake_buddy_list, "populate", ({keys: user_ids}) => {
            assert.deepEqual(user_ids, expected_user_ids);
        });

        activity.build_user_sidebar();
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
    const $user_filter = $(".user-list-filter");

    override(popovers, "hide_all", () => {});
    override(popovers, "hide_all_except_sidebars", () => {});
    override(popovers, "show_userlist_sidebar", () => {});
    override(resize, "resize_sidebars", () => {});

    page_params.realm_presence_disabled = true;

    assert.ok(!$("#user_search_section").hasClass("notdisplayed"));

    $user_filter.val("bla");

    $("#userlist-header").trigger("click");
    assert.ok($("#user_search_section").hasClass("notdisplayed"));
    assert.equal($user_filter.val(), "");

    $(".user-list-filter").closest = (selector) => {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create("sidebar").addClass("column-right");
    };

    $("#userlist-header").trigger("click");
    assert.equal($("#user_search_section").hasClass("notdisplayed"), false);
});

test("searching", () => {
    assert.equal(activity.searching(), false);
    $(".user-list-filter").trigger("focus");
    assert.equal(activity.searching(), true);
    $(".user-list-filter").trigger("blur");
    assert.equal(activity.searching(), false);
});
