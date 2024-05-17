"use strict";

const {strict: assert} = require("assert");

const {
    clear_buddy_list,
    override_user_matches_narrow,
    buddy_list_add_user_matching_view,
    buddy_list_add_other_user,
    stub_buddy_list_elements,
} = require("./lib/buddy_list");
const {mock_esm, set_global, with_overrides, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");
const {current_user, page_params, realm, user_settings} = require("./lib/zpage_params");

const $window_stub = $.create("window-stub");
set_global("to_$", () => $window_stub);
$(window).idle = noop;

const _document = {
    hasFocus() {
        return true;
    },
};

const channel = mock_esm("../src/channel");
const padded_widget = mock_esm("../src/padded_widget");
const pm_list = mock_esm("../src/pm_list");
const popovers = mock_esm("../src/popovers");
const resize = mock_esm("../src/resize");
const settings_data = mock_esm("../src/settings_data");
const sidebar_ui = mock_esm("../src/sidebar_ui");
const scroll_util = mock_esm("../src/scroll_util");
const watchdog = mock_esm("../src/watchdog");

set_global("document", _document);

const huddle_data = zrequire("huddle_data");
const keydown_util = zrequire("keydown_util");
const muted_users = zrequire("muted_users");
const presence = zrequire("presence");
const people = zrequire("people");
const buddy_data = zrequire("buddy_data");
const {buddy_list} = zrequire("buddy_list");
const activity = zrequire("activity");
const activity_ui = zrequire("activity_ui");
const stream_data = zrequire("stream_data");
const peer_data = zrequire("peer_data");
const message_lists = zrequire("message_lists");
const util = zrequire("util");
const {Filter} = zrequire("../src/filter");

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
const mark = {
    email: "mark@zulip.com",
    user_id: 4,
    full_name: "Marky Mark",
};
const norbert = {
    email: "norbert@zulip.com",
    user_id: 5,
    full_name: "Norbert Oswald",
};

const zoe = {
    email: "zoe@example.com",
    user_id: 6,
    full_name: "Zoe Yang",
};

people.add_active_user(alice);
people.add_active_user(fred);
people.add_active_user(jill);
people.add_active_user(mark);
people.add_active_user(norbert);
people.add_active_user(zoe);
people.add_active_user(me);
people.initialize_current_user(me.user_id);

const $alice_stub = $.create("alice stub");
const $fred_stub = $.create("fred stub");

const rome_sub = {name: "Rome", subscribed: true, stream_id: 1001};
function add_sub_and_set_as_current_narrow(sub) {
    stream_data.add_sub(sub);
    const filter = new Filter([{operator: "stream", operand: sub.name}]);
    message_lists.set_current({
        data: {
            filter,
        },
    });
}

function test(label, f) {
    run_test(label, (helpers) => {
        user_settings.presence_enabled = true;
        // Simulate a small window by having the
        // fill_screen_with_content render the entire
        // list in one pass.  We will do more refined
        // testing in the buddy_list node tests.
        helpers.override(buddy_list, "fill_screen_with_content", () => {
            buddy_list.render_more({
                chunk_size: 100,
            });
        });

        stub_buddy_list_elements();
        helpers.override(buddy_list, "render_section_headers", noop);
        helpers.override(buddy_list, "render_view_user_list_links", noop);

        presence.presence_info.set(alice.user_id, {status: "active"});
        presence.presence_info.set(fred.user_id, {status: "active"});
        presence.presence_info.set(jill.user_id, {status: "active"});
        presence.presence_info.set(mark.user_id, {status: "idle"});
        presence.presence_info.set(norbert.user_id, {status: "active"});
        presence.presence_info.set(zoe.user_id, {status: "active"});
        presence.presence_info.set(me.user_id, {status: "active"});

        clear_buddy_list(buddy_list);
        muted_users.set_muted_users([]);

        activity.clear_for_testing();
        activity_ui.set_cursor_and_filter();

        f(helpers);

        presence.clear_internal_data();
    });
}

run_test("reload_defaults", () => {
    activity.clear_for_testing();
    activity_ui.clear_for_testing();
    blueslip.expect("warn", "get_filter_text() is called before initialization");
    assert.equal(activity_ui.get_filter_text(), "");
});

test("get_status", () => {
    page_params.realm_users = [];
    current_user.user_id = 999;

    assert.equal(presence.get_status(current_user.user_id), "active");
    assert.equal(presence.get_status(alice.user_id), "active");
    assert.equal(presence.get_status(mark.user_id), "idle");
    assert.equal(presence.get_status(fred.user_id), "active");

    user_settings.presence_enabled = false;
    assert.equal(presence.get_status(current_user.user_id), "offline");
    user_settings.presence_enabled = true;
    assert.equal(presence.get_status(current_user.user_id), "active");

    presence.presence_info.delete(zoe.user_id);
    assert.equal(presence.get_status(zoe.user_id), "offline");

    presence.presence_info.set(alice.user_id, {status: "whatever"});
    assert.equal(presence.get_status(alice.user_id), "whatever");
});

test("sort_users", () => {
    const user_ids = [alice.user_id, fred.user_id, jill.user_id];

    presence.presence_info.delete(alice.user_id);

    buddy_data.sort_users(user_ids);

    assert.deepEqual(user_ids, [fred.user_id, jill.user_id, alice.user_id]);
});

test("huddle_data.process_loaded_messages", () => {
    // TODO: move this to a module for just testing `huddle_data`

    const huddle1 = "jill@zulip.com,norbert@zulip.com";
    const timestamp1 = 1382479029; // older

    const huddle2 = "alice@zulip.com,fred@zulip.com";
    const timestamp2 = 1382479033; // newer

    const old_timestamp = 1382479000;

    const messages = [
        {
            type: "private",
            display_recipient: [{id: jill.user_id}, {id: norbert.user_id}],
            timestamp: timestamp1,
        },
        {
            type: "stream",
        },
        // direct message to myself
        {
            type: "private",
            display_recipient: [{id: me.user_id}],
        },
        {
            type: "private",
            display_recipient: [{id: alice.user_id}, {id: fred.user_id}],
            timestamp: timestamp2,
        },
        {
            type: "private",
            display_recipient: [{id: fred.user_id}, {id: alice.user_id}],
            timestamp: old_timestamp,
        },
    ];

    huddle_data.process_loaded_messages(messages);

    const user_ids_string1 = people.emails_strings_to_user_ids_string(huddle1);
    const user_ids_string2 = people.emails_strings_to_user_ids_string(huddle2);
    assert.deepEqual(huddle_data.get_huddles(), [user_ids_string2, user_ids_string1]);
});

test("presence_list_full_update", ({override, mock_template}) => {
    override(padded_widget, "update_padding", noop);
    let presence_rows = [];
    mock_template("presence_rows.hbs", false, (data) => {
        presence_rows = [...presence_rows, ...data.presence_rows];
        return "<presence-rows-stub>";
    });

    $("input.user-list-filter").trigger("focus");

    const user_ids = activity_ui.build_user_sidebar();

    assert.deepEqual(user_ids, [
        me.user_id,
        alice.user_id,
        fred.user_id,
        jill.user_id,
        norbert.user_id,
        zoe.user_id,
        mark.user_id,
    ]);

    assert.equal(presence_rows.length, 7);
    assert.equal(presence_rows[0].user_id, me.user_id);
});

function simulate_right_column_buddy_list() {
    $("input.user-list-filter").closest = (selector) => {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create("right-sidebar").addClass("column-right");
    };
}

test("direct_message_update_dom_counts", () => {
    const $count = $.create("alice-unread-count");
    const pm_key = alice.user_id.toString();
    const $li = $.create("alice stub");
    buddy_list_add_user_matching_view(pm_key, $li);
    $li.set_find_results(".unread_count", $count);
    $count.set_parents_result("li", $li);

    const counts = new Map();
    counts.set(pm_key, 5);
    $li.addClass("user_sidebar_entry");

    activity_ui.update_dom_with_unread_counts({pm_count: counts});
    assert.equal($count.text(), "5");

    counts.set(pm_key, 0);

    activity_ui.update_dom_with_unread_counts({pm_count: counts});
    assert.equal($count.text(), "");
});

test("handlers", ({override, override_rewire, mock_template}) => {
    let filter_key_handlers;

    mock_template("presence_rows.hbs", false, () => "<presence-rows-stub>");

    override(keydown_util, "handle", (opts) => {
        filter_key_handlers = opts.handlers;
    });
    override(scroll_util, "scroll_element_into_container", noop);
    override(padded_widget, "update_padding", noop);
    override(popovers, "hide_all", noop);
    override(sidebar_ui, "hide_all", noop);
    override(sidebar_ui, "show_userlist_sidebar", noop);
    override(resize, "resize_sidebars", noop);

    // This is kind of weak coverage; we are mostly making sure that
    // keys and clicks got mapped to functions that don't crash.
    const $me_li = $.create("me stub");
    const $alice_li = $.create("alice stub");
    const $fred_li = $.create("fred stub");

    // Simulate a small window by having the
    // fill_screen_with_content render the entire
    // list in one pass.  We will do more refined
    // testing in the buddy_list node tests.
    override(buddy_list, "fill_screen_with_content", () => {
        buddy_list.render_more({
            chunk_size: 100,
        });
        buddy_list_add_user_matching_view(me.user_id, $me_li);
        buddy_list_add_user_matching_view(alice.user_id, $alice_li);
        buddy_list_add_user_matching_view(fred.user_id, $fred_li);
    });

    let narrowed;

    function narrow_by_email(email) {
        assert.equal(email, "alice@zulip.com");
        narrowed = true;
    }

    function init() {
        $.clear_all_elements();
        stub_buddy_list_elements();

        buddy_list.start_scroll_handler = noop;
        override_rewire(util, "call_function_periodically", noop);
        override_rewire(activity, "send_presence_to_server", noop);
        activity_ui.initialize({narrow_by_email});

        buddy_list.populate({
            all_user_ids: [me.user_id, alice.user_id, fred.user_id],
        });
    }

    (function test_filter_keys() {
        init();
        activity_ui.user_cursor.go_to(alice.user_id);
        filter_key_handlers.ArrowDown();
        filter_key_handlers.ArrowUp();
    })();

    (function test_click_filter() {
        init();
        const e = {
            stopPropagation() {},
        };

        const handler = $("input.user-list-filter").get_on_handler("focus");
        handler(e);
    })();

    (function test_click_header_filter() {
        init();
        const e = {};
        const handler = $("#userlist-header").get_on_handler("click");

        simulate_right_column_buddy_list();

        handler(e);
        // and click again
        handler(e);
    })();

    (function test_enter_key() {
        init();

        $("input.user-list-filter").val("al");
        narrowed = false;
        activity_ui.user_cursor.go_to(alice.user_id);
        filter_key_handlers.Enter();
        assert.ok(narrowed);

        // get line coverage for cleared case
        activity_ui.user_cursor.clear();
        filter_key_handlers.Enter();
    })();

    (function test_click_handler() {
        init();
        // We wire up the click handler in click_handlers.js,
        // so this just tests the called function.
        narrowed = false;
        activity_ui.narrow_for_user({$li: $alice_li});
        assert.ok(narrowed);
    })();

    (function test_blur_filter() {
        init();
        const e = {};
        const handler = $("input.user-list-filter").get_on_handler("blur");
        handler(e);
    })();
});

test("first/prev/next", ({override, override_rewire, mock_template}) => {
    override_rewire(buddy_data, "user_matches_narrow", override_user_matches_narrow);
    mock_template("presence_rows.hbs", false, () => "<presence-rows-stub>");
    override(padded_widget, "update_padding", noop);
    stub_buddy_list_elements();

    // empty list
    assert.equal(buddy_list.first_key(), undefined);
    blueslip.reset();
    blueslip.expect("error", "Couldn't find key in buddy list");
    assert.equal(buddy_list.prev_key(alice.user_id), undefined);
    blueslip.reset();
    blueslip.expect("error", "Couldn't find key in buddy list");
    assert.equal(buddy_list.next_key(alice.user_id), undefined);
    blueslip.reset();

    // one user matching the view
    clear_buddy_list(buddy_list);
    buddy_list_add_user_matching_view(alice.user_id, $alice_stub);
    buddy_list.populate({
        all_user_ids: [alice.user_id],
    });
    assert.equal(buddy_list.first_key(), alice.user_id);
    assert.equal(buddy_list.prev_key(alice.user_id), undefined);
    assert.equal(buddy_list.next_key(alice.user_id), undefined);

    // two users matching the view
    clear_buddy_list(buddy_list);
    buddy_list_add_user_matching_view(alice.user_id, $alice_stub);
    buddy_list_add_user_matching_view(fred.user_id, $fred_stub);
    buddy_list.populate({
        all_user_ids: [alice.user_id, fred.user_id],
    });
    assert.equal(buddy_list.first_key(), alice.user_id);
    assert.equal(buddy_list.prev_key(alice.user_id), undefined);
    assert.equal(buddy_list.prev_key(fred.user_id), alice.user_id);
    assert.equal(buddy_list.next_key(alice.user_id), fred.user_id);
    assert.equal(buddy_list.next_key(fred.user_id), undefined);

    // one other user
    clear_buddy_list(buddy_list);
    buddy_list_add_other_user(fred.user_id, $fred_stub);
    buddy_list.populate({
        all_user_ids: [fred.user_id],
    });
    assert.equal(buddy_list.first_key(), fred.user_id);
    assert.equal(buddy_list.prev_key(fred.user_id), undefined);
    assert.equal(buddy_list.next_key(fred.user_id), undefined);

    // two other users
    clear_buddy_list(buddy_list);
    buddy_list_add_other_user(alice.user_id, $alice_stub);
    buddy_list_add_other_user(fred.user_id, $fred_stub);
    buddy_list.populate({
        all_user_ids: [alice.user_id, fred.user_id],
    });
    assert.equal(buddy_list.first_key(), alice.user_id);
    assert.equal(buddy_list.prev_key(alice.user_id), undefined);
    assert.equal(buddy_list.prev_key(fred.user_id), alice.user_id);
    assert.equal(buddy_list.next_key(alice.user_id), fred.user_id);
    assert.equal(buddy_list.next_key(fred.user_id), undefined);

    // one user matching the view, and one other user
    clear_buddy_list(buddy_list);
    buddy_list_add_user_matching_view(alice.user_id, $alice_stub);
    buddy_list_add_other_user(alice.user_id, $fred_stub);
    buddy_list.populate({
        all_user_ids: [alice.user_id, fred.user_id],
    });
    assert.equal(buddy_list.first_key(), alice.user_id);
    assert.equal(buddy_list.prev_key(alice.user_id), undefined);
    assert.equal(buddy_list.prev_key(fred.user_id), alice.user_id);
    assert.equal(buddy_list.next_key(alice.user_id), fred.user_id);
    assert.equal(buddy_list.next_key(fred.user_id), undefined);
});

test("render_empty_user_list_message", ({override, mock_template}) => {
    const empty_list_message = "No matching users.";
    mock_template("empty_list_widget_for_list.hbs", false, (data) => {
        assert.equal(data.empty_list_message, empty_list_message);
        return "<empty-list-stub>";
    });

    let $appended_data;
    override(buddy_list, "$container", {
        append($data) {
            $appended_data = $data;
        },
        attr(name) {
            assert.equal(name, "data-search-results-empty");
            return empty_list_message;
        },
        children: () => [],
    });

    activity_ui.render_empty_user_list_message_if_needed(buddy_list.$container);
    assert.equal($appended_data.selector, "<empty-list-stub>");
});

test("insert_one_user_into_empty_list", ({override, mock_template}) => {
    user_settings.user_list_style = 2;

    override(padded_widget, "update_padding", noop);
    mock_template("presence_row.hbs", true, (data, html) => {
        assert.deepEqual(data, {
            href: "#narrow/dm/1-Alice-Smith",
            name: "Alice Smith",
            user_id: 1,
            is_current_user: false,
            num_unread: 0,
            user_circle_class: "user_circle_green",
            status_emoji_info: undefined,
            status_text: undefined,
            user_list_style: {
                COMPACT: false,
                WITH_STATUS: true,
                WITH_AVATAR: false,
            },
            should_add_guest_user_indicator: false,
        });
        assert.ok(html.startsWith("<li data-user-id="));
        return html;
    });

    let $users_matching_view_appended;
    override(buddy_list.$users_matching_view_container, "append", ($element) => {
        $users_matching_view_appended = $element;
    });
    let $other_users_appended;
    override(buddy_list.$other_users_container, "append", ($element) => {
        $other_users_appended = $element;
    });

    add_sub_and_set_as_current_narrow(rome_sub);

    buddy_list_add_user_matching_view(alice.user_id, $alice_stub);
    peer_data.set_subscribers(rome_sub.stream_id, [alice.user_id]);
    activity_ui.redraw_user(alice.user_id);
    assert.ok($users_matching_view_appended.selector.includes('data-user-id="1"'));
    assert.ok($users_matching_view_appended.selector.includes("user_circle_green"));

    clear_buddy_list(buddy_list);
    buddy_list_add_other_user(alice.user_id, $alice_stub);
    peer_data.set_subscribers(rome_sub.stream_id, []);
    activity_ui.redraw_user(alice.user_id);
    assert.ok($other_users_appended.selector.includes('data-user-id="1"'));
    assert.ok($other_users_appended.selector.includes("user_circle_green"));
});

test("insert_alice_then_fred", ({override, mock_template}) => {
    mock_template("presence_row.hbs", true, (_data, html) => html);

    let $other_users_appended;
    override(buddy_list.$other_users_container, "append", ($element) => {
        $other_users_appended = $element;
    });
    override(padded_widget, "update_padding", noop);

    activity_ui.redraw_user(alice.user_id);
    assert.ok($other_users_appended.selector.includes('data-user-id="1"'));
    assert.ok($other_users_appended.selector.includes("user_circle_green"));

    activity_ui.redraw_user(fred.user_id);
    assert.ok($other_users_appended.selector.includes('data-user-id="2"'));
    assert.ok($other_users_appended.selector.includes("user_circle_green"));
});

test("insert_fred_then_alice_then_rename, both as users matching view", ({
    override,
    mock_template,
}) => {
    mock_template("presence_row.hbs", true, (_data, html) => html);

    add_sub_and_set_as_current_narrow(rome_sub);
    peer_data.set_subscribers(rome_sub.stream_id, [alice.user_id, fred.user_id]);

    let $users_matching_view_appended;
    override(buddy_list.$users_matching_view_container, "append", ($element) => {
        $users_matching_view_appended = $element;
    });
    override(padded_widget, "update_padding", noop);
    buddy_list_add_user_matching_view(alice.user_id, $alice_stub);
    buddy_list_add_user_matching_view(fred.user_id, $fred_stub);

    activity_ui.redraw_user(fred.user_id);
    assert.ok($users_matching_view_appended.selector.includes('data-user-id="2"'));
    assert.ok($users_matching_view_appended.selector.includes("user_circle_green"));

    let $inserted;
    $fred_stub.before = ($element) => {
        $inserted = $element;
    };

    let fred_removed;
    $fred_stub.remove = () => {
        fred_removed = true;
    };

    activity_ui.redraw_user(alice.user_id);
    assert.ok($inserted.selector.includes('data-user-id="1"'));
    assert.ok($inserted.selector.includes("user_circle_green"));

    // Next rename fred to Aaron.
    const fred_with_new_name = {
        email: fred.email,
        user_id: fred.user_id,
        full_name: "Aaron",
    };
    people.add_active_user(fred_with_new_name);

    $alice_stub.before = ($element) => {
        $inserted = $element;
    };

    activity_ui.redraw_user(fred_with_new_name.user_id);
    assert.ok(fred_removed);
    assert.ok($users_matching_view_appended.selector.includes('data-user-id="2"'));

    // restore old Fred data
    people.add_active_user(fred);
});

test("insert_fred_then_alice_then_rename, both as other users", ({override, mock_template}) => {
    mock_template("presence_row.hbs", true, (_data, html) => html);

    add_sub_and_set_as_current_narrow(rome_sub);
    peer_data.set_subscribers(rome_sub.stream_id, []);

    let $other_users_appended;
    override(buddy_list.$other_users_container, "append", ($element) => {
        $other_users_appended = $element;
    });
    override(padded_widget, "update_padding", noop);

    buddy_list_add_other_user(alice.user_id, $alice_stub);
    buddy_list_add_other_user(fred.user_id, $fred_stub);

    activity_ui.redraw_user(fred.user_id);
    assert.ok($other_users_appended.selector.includes('data-user-id="2"'));
    assert.ok($other_users_appended.selector.includes("user_circle_green"));

    let $inserted;
    $fred_stub.before = ($element) => {
        $inserted = $element;
    };

    let fred_removed;
    $fred_stub.remove = () => {
        fred_removed = true;
    };

    activity_ui.redraw_user(alice.user_id);
    assert.ok($inserted.selector.includes('data-user-id="1"'));
    assert.ok($inserted.selector.includes("user_circle_green"));

    // Next rename fred to Aaron.
    const fred_with_new_name = {
        email: fred.email,
        user_id: fred.user_id,
        full_name: "Aaron",
    };
    people.add_active_user(fred_with_new_name);

    $alice_stub.before = ($element) => {
        $inserted = $element;
    };

    activity_ui.redraw_user(fred_with_new_name.user_id);
    assert.ok(fred_removed);
    assert.ok($other_users_appended.selector.includes('data-user-id="2"'));

    // restore old Fred data
    people.add_active_user(fred);
});

test("insert_unfiltered_user_with_filter", () => {
    // This test only tests that we do not explode when
    // try to insert Fred into a list where he does not
    // match the search filter.
    const $user_filter = $("input.user-list-filter");
    $user_filter.val("do-not-match-filter");
    activity_ui.redraw_user(fred.user_id);
});

test("realm_presence_disabled", () => {
    realm.realm_presence_disabled = true;

    activity_ui.redraw_user();
    activity_ui.build_user_sidebar();
});

test("redraw_muted_user", () => {
    muted_users.add_muted_user(mark.user_id);
    activity_ui.redraw_user(mark.user_id);
    assert.equal($("#buddy-list-users-matching-view").html(), "never-been-set");
});

test("update_presence_info", ({override}) => {
    override(pm_list, "update_private_messages", noop);

    realm.realm_presence_disabled = false;
    realm.server_presence_ping_interval_seconds = 60;
    realm.server_presence_offline_threshold_seconds = 200;

    const server_time = 500;
    const info = {
        website: {
            status: "active",
            timestamp: server_time,
        },
    };

    const $alice_li = $.create("alice stub");
    buddy_list_add_user_matching_view(alice.user_id, $alice_li);

    let inserted;
    override(buddy_list, "insert_or_move", () => {
        inserted = true;
    });

    presence.presence_info.delete(me.user_id);
    activity_ui.update_presence_info(me.user_id, info, server_time);
    assert.ok(inserted);
    assert.deepEqual(presence.presence_info.get(me.user_id).status, "active");

    presence.presence_info.delete(alice.user_id);
    activity_ui.update_presence_info(alice.user_id, info, server_time);
    assert.ok(inserted);

    const expected = {status: "active", last_active: 500};
    assert.deepEqual(presence.presence_info.get(alice.user_id), expected);

    // Test invalid and inaccessible user IDs.
    const invalid_user_id = 99;
    activity_ui.update_presence_info(invalid_user_id, info, server_time);
    assert.equal(presence.presence_info.get(invalid_user_id), undefined);

    const inaccessible_user_id = 10;
    settings_data.user_can_access_all_other_users = () => false;
    const inaccessible_user = people.make_user(
        inaccessible_user_id,
        "user10@zulipdev.com",
        "Unknown user",
    );
    people._add_user(inaccessible_user);
    activity_ui.update_presence_info(inaccessible_user_id, info, server_time);
    assert.equal(presence.presence_info.get(inaccessible_user_id), undefined);
});

test("initialize", ({override, mock_template}) => {
    override(pm_list, "update_private_messages", noop);
    override(watchdog, "check_for_unsuspend", noop);
    override(buddy_list, "fill_screen_with_content", noop);

    let payload;
    override(channel, "post", (arg) => {
        if (payload === undefined) {
            // This "if" block is added such that we can execute "success"
            // function when want_redraw is true.
            payload = arg;
        }
    });

    function clear() {
        $.clear_all_elements();
        buddy_list.$users_matching_view_container = $("#buddy-list-users-matching-view");
        buddy_list.$users_matching_view_container.append = noop;
        buddy_list.$other_users_container = $("#buddy-list-other-users");
        buddy_list.$other_users_container.append = noop;
        stub_buddy_list_elements();
        mock_template("empty_list_widget_for_list.hbs", false, () => "<empty-list-stub>");
        clear_buddy_list(buddy_list);
        page_params.presences = {};
    }

    clear();

    let scroll_handler_started;
    buddy_list.start_scroll_handler = () => {
        scroll_handler_started = true;
    };

    activity.mark_client_idle();

    $(window).off("focus");

    let set_timeout_function_called = false;
    set_global("setTimeout", (func) => {
        if (set_timeout_function_called) {
            // This conditional is needed to avoid indefinite calls.
            return;
        }
        set_timeout_function_called = true;
        func();
    });

    activity.initialize();
    activity_ui.initialize({narrow_by_email() {}});
    payload.success({
        zephyr_mirror_active: true,
        presences: {},
        msg: "",
        result: "success",
        server_timestamp: 0,
    });
    $(window).trigger("focus");
    clear();

    assert.ok(scroll_handler_started);
    assert.ok(!activity.new_user_input);
    assert.ok(!$("#zephyr-mirror-error").hasClass("show"));
    assert.equal(activity.compute_active_status(), "active");

    $(window).idle = (params) => {
        params.onIdle();
    };
    payload = undefined;
    set_timeout_function_called = false;

    $(window).off("focus");
    activity.initialize();
    activity_ui.initialize({narrow_by_email() {}});
    payload.success({
        zephyr_mirror_active: false,
        presences: {},
        msg: "",
        result: "success",
        server_timestamp: 0,
    });

    assert.ok($("#zephyr-mirror-error").hasClass("show"));
    assert.ok(!activity.new_user_input);
    assert.equal(activity.compute_active_status(), "idle");

    // Exercise the mousemove handler, which just
    // sets a flag.
    $("html").get_on_handler("mousemove")();

    clear();
});

test("electron_bridge", ({override_rewire}) => {
    override_rewire(activity, "send_presence_to_server", noop);

    function with_bridge_idle(bridge_idle, f) {
        with_overrides(({override}) => {
            override(window, "electron_bridge", {
                get_idle_on_system: () => bridge_idle,
            });
            return f();
        });
    }

    with_bridge_idle(true, () => {
        activity.mark_client_idle();
        assert.equal(activity.compute_active_status(), "idle");
        activity.mark_client_active();
        assert.equal(activity.compute_active_status(), "idle");
    });

    with_overrides(({override}) => {
        override(window, "electron_bridge", undefined);
        activity.mark_client_idle();
        assert.equal(activity.compute_active_status(), "idle");
        activity.mark_client_active();
        assert.equal(activity.compute_active_status(), "active");
    });

    with_bridge_idle(false, () => {
        activity.mark_client_idle();
        assert.equal(activity.compute_active_status(), "active");
        activity.mark_client_active();
        assert.equal(activity.compute_active_status(), "active");
    });
});

test("test_send_or_receive_no_presence_for_spectator", () => {
    page_params.is_spectator = true;
    activity.send_presence_to_server();
});
