"use strict";

const {strict: assert} = require("assert");

const {mock_module, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const window_stub = $.create("window-stub");
set_global("to_$", () => window_stub);
$(window).idle = () => {};

let filter_key_handlers;

const page_params = set_global("page_params", {
    realm_users: [],
    user_id: 999,
});

const _document = {
    hasFocus() {
        return true;
    },
};

const compose_state = mock_module("compose_state");
const channel = mock_module("channel");

mock_module("padded_widget", {
    update_padding: () => {},
});
mock_module("keydown_util", {
    handle: (opts) => {
        filter_key_handlers = opts.handlers;
    },
});
mock_module("pm_list", {
    update_private_messages: () => {},
});
mock_module("popovers", {
    hide_all_except_sidebars() {},
    hide_all() {},
    show_userlist_sidebar() {},
});
mock_module("resize", {
    resize_sidebars: () => {},
    resize_page_components: () => {},
});
mock_module("scroll_util", {
    scroll_element_into_container: () => {},
});
mock_module("server_events", {
    check_for_unsuspend() {},
});
mock_module("stream_popover", {
    show_streamlist_sidebar() {},
});
set_global("document", _document);

const huddle_data = zrequire("huddle_data");
const compose_fade = zrequire("compose_fade");
const narrow = zrequire("narrow");
const presence = zrequire("presence");
const people = zrequire("people");
const buddy_data = zrequire("buddy_data");
const {buddy_list} = zrequire("buddy_list");
const user_status = zrequire("user_status");
const activity = zrequire("activity");

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

const presence_info = new Map();
presence_info.set(alice.user_id, {status: "inactive"});
presence_info.set(fred.user_id, {status: "active"});
presence_info.set(jill.user_id, {status: "active"});

presence.__Rewire__("presence_info", presence_info);

// Simulate a small window by having the
// fill_screen_with_content render the entire
// list in one pass.  We will do more refined
// testing in the buddy_list node tests.
buddy_list.fill_screen_with_content = () => {
    buddy_list.render_more({
        chunk_size: 100,
    });
};

run_test("reload_defaults", () => {
    blueslip.expect("warn", "get_filter_text() is called before initialization");
    assert.equal(activity.get_filter_text(), "");
});

run_test("get_status", () => {
    assert.equal(presence.get_status(page_params.user_id), "active");
    assert.equal(presence.get_status(alice.user_id), "inactive");
    assert.equal(presence.get_status(fred.user_id), "active");
    assert.equal(presence.get_status(zoe.user_id), "offline");
});

run_test("sort_users", () => {
    const user_ids = [alice.user_id, fred.user_id, jill.user_id];

    buddy_data.sort_users(user_ids);

    assert.deepEqual(user_ids, [fred.user_id, jill.user_id, alice.user_id]);
});

run_test("huddle_data.process_loaded_messages", () => {
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
        {
            type: "private",
            display_recipient: [{id: me.user_id}], // PM to myself
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

presence.__Rewire__("presence_info", new Map());
presence.presence_info.set(alice.user_id, {status: activity.IDLE});
presence.presence_info.set(fred.user_id, {status: activity.ACTIVE});
presence.presence_info.set(jill.user_id, {status: activity.ACTIVE});
presence.presence_info.set(mark.user_id, {status: activity.IDLE});
presence.presence_info.set(norbert.user_id, {status: activity.ACTIVE});
presence.presence_info.set(zoe.user_id, {status: activity.ACTIVE});
presence.presence_info.set(me.user_id, {status: activity.ACTIVE});

function clear_buddy_list() {
    buddy_list.populate({
        keys: [],
    });
}

function test_ui(label, f) {
    run_test(label, (override) => {
        clear_buddy_list();
        f(override);
    });
}

test_ui("presence_list_full_update", () => {
    activity.set_cursor_and_filter();

    $(".user-list-filter").trigger("focus");
    compose_state.private_message_recipient = () => fred.email;
    compose_fade.set_focused_recipient("private");

    const user_ids = activity.build_user_sidebar();

    assert.deepEqual(user_ids, [
        me.user_id,
        fred.user_id,
        jill.user_id,
        norbert.user_id,
        zoe.user_id,
        alice.user_id,
        mark.user_id,
    ]);
});

function simulate_right_column_buddy_list() {
    $(".user-list-filter").closest = (selector) => {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create("right-sidebar").addClass("column-right");
    };
}

function simulate_left_column_buddy_list() {
    $(".user-list-filter").closest = (selector) => {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create("left-sidebar").addClass("column-left");
    };
}

function buddy_list_add(user_id, stub) {
    if (stub.attr) {
        stub.attr("data-user-id", user_id);
    }
    stub.length = 1;
    const sel = `li.user_sidebar_entry[data-user-id='${CSS.escape(user_id)}']`;
    $("#user_presences").set_find_results(sel, stub);
}

test_ui("PM_update_dom_counts", () => {
    const value = $.create("alice-value");
    const count = $.create("alice-count");
    const pm_key = alice.user_id.toString();
    const li = $.create("alice stub");
    buddy_list_add(pm_key, li);
    count.set_find_results(".value", value);
    li.set_find_results(".count", count);
    count.set_parents_result("li", li);

    const counts = new Map();
    counts.set(pm_key, 5);
    li.addClass("user_sidebar_entry");

    activity.update_dom_with_unread_counts({pm_count: counts});
    assert(li.hasClass("user-with-count"));
    assert.equal(value.text(), "5");

    counts.set(pm_key, 0);

    activity.update_dom_with_unread_counts({pm_count: counts});
    assert(!li.hasClass("user-with-count"));
    assert.equal(value.text(), "");
});

test_ui("handlers", (override) => {
    // This is kind of weak coverage; we are mostly making sure that
    // keys and clicks got mapped to functions that don't crash.
    let me_li;
    let alice_li;
    let fred_li;

    let narrowed;

    override(narrow, "by", (method, email) => {
        assert.equal(email, "alice@zulip.com");
        narrowed = true;
    });

    function init() {
        $.clear_all_elements();
        buddy_list.populate({
            keys: [me.user_id, alice.user_id, fred.user_id],
        });
        activity.set_cursor_and_filter();

        me_li = $.create("me stub");
        alice_li = $.create("alice stub");
        fred_li = $.create("fred stub");

        buddy_list_add(me.user_id, me_li);
        buddy_list_add(alice.user_id, alice_li);
        buddy_list_add(fred.user_id, fred_li);
    }

    (function test_filter_keys() {
        init();
        activity.user_cursor.go_to(alice.user_id);
        filter_key_handlers.down_arrow();
        filter_key_handlers.up_arrow();
    })();

    (function test_click_filter() {
        init();
        const e = {
            stopPropagation: () => {},
        };

        const handler = $(".user-list-filter").get_on_handler("focus");
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

        $(".user-list-filter").val("al");
        narrowed = false;
        activity.user_cursor.go_to(alice.user_id);
        filter_key_handlers.enter_key();
        assert(narrowed);

        // get line coverage for cleared case
        activity.user_cursor.clear();
        filter_key_handlers.enter_key();
    })();

    (function test_click_handler() {
        init();
        // We wire up the click handler in click_handlers.js,
        // so this just tests the called function.
        narrowed = false;
        activity.narrow_for_user({li: alice_li});
        assert(narrowed);
    })();

    (function test_blur_filter() {
        init();
        const e = {};
        const handler = $(".user-list-filter").get_on_handler("blur");
        handler(e);
    })();
});

presence.__Rewire__("presence_info", new Map());
presence.presence_info.set(alice.user_id, {status: activity.ACTIVE});
presence.presence_info.set(fred.user_id, {status: activity.ACTIVE});
presence.presence_info.set(jill.user_id, {status: activity.ACTIVE});
presence.presence_info.set(mark.user_id, {status: activity.IDLE});
presence.presence_info.set(norbert.user_id, {status: activity.ACTIVE});
presence.presence_info.set(zoe.user_id, {status: activity.ACTIVE});

test_ui("first/prev/next", () => {
    clear_buddy_list();

    assert.equal(buddy_list.first_key(), undefined);
    assert.equal(buddy_list.prev_key(alice.user_id), undefined);
    assert.equal(buddy_list.next_key(alice.user_id), undefined);

    buddy_list.container.append = () => {};

    activity.redraw_user(alice.user_id);
    activity.redraw_user(fred.user_id);

    assert.equal(buddy_list.first_key(), alice.user_id);
    assert.equal(buddy_list.prev_key(alice.user_id), undefined);
    assert.equal(buddy_list.prev_key(fred.user_id), alice.user_id);

    assert.equal(buddy_list.next_key(alice.user_id), fred.user_id);
    assert.equal(buddy_list.next_key(fred.user_id), undefined);
});

test_ui("filter_user_ids", () => {
    const user_filter = $(".user-list-filter");
    user_filter.val(""); // no search filter
    activity.set_cursor_and_filter();

    function get_user_ids() {
        const filter_text = activity.get_filter_text();
        const user_ids = buddy_data.get_filtered_and_sorted_user_ids(filter_text);
        return user_ids;
    }

    let user_ids = buddy_data.get_filtered_and_sorted_user_ids();
    assert.deepEqual(user_ids, [
        alice.user_id,
        fred.user_id,
        jill.user_id,
        norbert.user_id,
        zoe.user_id,
        mark.user_id,
    ]);

    user_filter.val("abc"); // no match
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, []);

    user_filter.val("fred"); // match fred
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, [fred.user_id]);

    user_filter.val("fred,alice"); // match fred and alice
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);

    user_filter.val("fr,al"); // match fred and alice partials
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);

    user_filter.val("fr|al"); // test | as OR-operator
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);

    presence.presence_info.set(alice.user_id, {status: activity.IDLE});
    user_filter.val("fr,al"); // match fred and alice partials and idle user
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, [fred.user_id, alice.user_id]);

    presence.presence_info.set(alice.user_id, {status: activity.ACTIVE});
    user_ids = get_user_ids();
    assert.deepEqual(user_ids, [alice.user_id, fred.user_id]);
});

test_ui("insert_one_user_into_empty_list", (override) => {
    let appended_html;
    override(buddy_list.container, "append", (html) => {
        appended_html = html;
    });

    activity.redraw_user(alice.user_id);
    assert(appended_html.indexOf('data-user-id="1"') > 0);
    assert(appended_html.indexOf("user_circle_green") > 0);
});

test_ui("insert_alice_then_fred", (override) => {
    let appended_html;
    override(buddy_list.container, "append", (html) => {
        appended_html = html;
    });

    activity.redraw_user(alice.user_id);
    assert(appended_html.indexOf('data-user-id="1"') > 0);
    assert(appended_html.indexOf("user_circle_green") > 0);

    activity.redraw_user(fred.user_id);
    assert(appended_html.indexOf('data-user-id="2"') > 0);
    assert(appended_html.indexOf("user_circle_green") > 0);
});

test_ui("insert_fred_then_alice_then_rename", (override) => {
    let appended_html;
    override(buddy_list.container, "append", (html) => {
        appended_html = html;
    });

    activity.redraw_user(fred.user_id);
    assert(appended_html.indexOf('data-user-id="2"') > 0);
    assert(appended_html.indexOf("user_circle_green") > 0);

    const fred_stub = $.create("fred-first");
    buddy_list_add(fred.user_id, fred_stub);

    let inserted_html;
    fred_stub.before = (html) => {
        inserted_html = html;
    };

    let fred_removed;
    fred_stub.remove = () => {
        fred_removed = true;
    };

    activity.redraw_user(alice.user_id);
    assert(inserted_html.indexOf('data-user-id="1"') > 0);
    assert(inserted_html.indexOf("user_circle_green") > 0);

    // Next rename fred to Aaron.
    const fred_with_new_name = {
        email: fred.email,
        user_id: fred.user_id,
        full_name: "Aaron",
    };
    people.add_active_user(fred_with_new_name);

    const alice_stub = $.create("alice-first");
    buddy_list_add(alice.user_id, alice_stub);

    alice_stub.before = (html) => {
        inserted_html = html;
    };

    activity.redraw_user(fred_with_new_name.user_id);
    assert(fred_removed);
    assert(appended_html.indexOf('data-user-id="2"') > 0);

    // restore old Fred data
    people.add_active_user(fred);
});

test_ui("insert_unfiltered_user_with_filter", () => {
    // This test only tests that we do not explode when
    // try to insert Fred into a list where he does not
    // match the search filter.
    activity.set_cursor_and_filter();

    const user_filter = $(".user-list-filter");
    user_filter.val("do-not-match-filter");
    activity.redraw_user(fred.user_id);
});

test_ui("realm_presence_disabled", () => {
    page_params.realm_presence_disabled = true;

    activity.redraw_user();
    activity.build_user_sidebar();
});

test_ui("clear_search", () => {
    activity.set_cursor_and_filter();

    $(".user-list-filter").val("somevalue");
    $("#clear_search_people_button").trigger("click");
    assert.equal($(".user-list-filter").val(), "");
    $("#clear_search_people_button").trigger("click");
    assert($("#user_search_section").hasClass("notdisplayed"));
});

test_ui("escape_search", () => {
    activity.set_cursor_and_filter();

    $(".user-list-filter").val("somevalue");
    activity.escape_search();
    assert.equal($(".user-list-filter").val(), "");
    activity.escape_search();
    assert($("#user_search_section").hasClass("notdisplayed"));
});

test_ui("initiate_search", () => {
    activity.set_cursor_and_filter();

    $(".user-list-filter").trigger("blur");
    simulate_right_column_buddy_list();
    activity.initiate_search();
    assert.equal($(".user-list-filter").is_focused(), true);

    simulate_left_column_buddy_list();
    activity.initiate_search();
    assert.equal($(".user-list-filter").is_focused(), true);
});

test_ui("toggle_filter_display", () => {
    activity.set_cursor_and_filter();

    activity.user_filter.toggle_filter_displayed();
    assert($("#user_search_section").hasClass("notdisplayed"));
    $(".user-list-filter").closest = (selector) => {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create("sidebar").addClass("column-right");
    };
    activity.user_filter.toggle_filter_displayed();
    assert.equal($("#user_search_section").hasClass("notdisplayed"), false);
});

test_ui("searching", () => {
    activity.set_cursor_and_filter();

    $(".user-list-filter").trigger("focus");
    assert.equal(activity.searching(), true);
    $(".user-list-filter").trigger("blur");
    assert.equal(activity.searching(), false);
});

test_ui("update_presence_info", (override) => {
    page_params.realm_presence_disabled = false;

    const server_time = 500;
    const info = {
        website: {
            status: "active",
            timestamp: server_time,
        },
    };

    override(buddy_data, "matches_filter", () => true);

    const alice_li = $.create("alice stub");
    buddy_list_add(alice.user_id, alice_li);

    let inserted;
    buddy_list.insert_or_move = () => {
        inserted = true;
    };

    presence.presence_info.delete(me.user_id);
    activity.update_presence_info(me.user_id, info, server_time);
    assert(inserted);
    assert.deepEqual(presence.presence_info.get(me.user_id).status, "active");

    presence.presence_info.delete(alice.user_id);
    activity.update_presence_info(alice.user_id, info, server_time);
    assert(inserted);

    const expected = {status: "active", last_active: 500};
    assert.deepEqual(presence.presence_info.get(alice.user_id), expected);
});

test_ui("initialize", (override) => {
    let payload;
    override(channel, "post", (arg) => {
        payload = arg;
    });

    function clear() {
        $.clear_all_elements();
        buddy_list.container = $("#user_presences");
        buddy_list.container.append = () => {};
        clear_buddy_list();
        page_params.presences = {};
    }

    clear();

    let scroll_handler_started;
    buddy_list.start_scroll_handler = () => {
        scroll_handler_started = true;
    };

    activity.__Rewire__("client_is_active", false);

    $(window).off("focus");
    activity.initialize();
    payload.success({});
    $(window).trigger("focus");
    clear();

    assert(scroll_handler_started);
    assert(!activity.new_user_input);
    assert(!$("#zephyr-mirror-error").hasClass("show"));
    assert(activity.client_is_active);
    $(window).idle = (params) => {
        params.onIdle();
    };

    set_global("setInterval", (func) => func());

    $(window).off("focus");
    activity.initialize();
    payload.success({
        zephyr_mirror_active: false,
        presences: {},
    });

    assert($("#zephyr-mirror-error").hasClass("show"));
    assert(!activity.new_user_input);
    assert(!activity.client_is_active);

    // Exercise the mousemove handler, which just
    // sets a flag.
    $("html").get_on_handler("mousemove")();

    clear();
});

run_test("away_status", () => {
    assert(!user_status.is_away(alice.user_id));
    activity.on_set_away(alice.user_id);
    assert(user_status.is_away(alice.user_id));
    activity.on_revoke_away(alice.user_id);
    assert(!user_status.is_away(alice.user_id));
});

test_ui("electron_bridge", () => {
    activity.__Rewire__("client_is_active", false);
    window.electron_bridge = undefined;
    assert.equal(activity.compute_active_status(), activity.IDLE);

    activity.__Rewire__("client_is_active", true);
    assert.equal(activity.compute_active_status(), activity.ACTIVE);

    window.electron_bridge = {
        get_idle_on_system: () => true,
    };
    assert.equal(activity.compute_active_status(), activity.IDLE);
    activity.__Rewire__("client_is_active", false);
    assert.equal(activity.compute_active_status(), activity.IDLE);

    window.electron_bridge = {
        get_idle_on_system: () => false,
    };
    assert.equal(activity.compute_active_status(), activity.ACTIVE);
    activity.__Rewire__("client_is_active", true);
    assert.equal(activity.compute_active_status(), activity.ACTIVE);
});

test_ui("test_send_or_receive_no_presence_for_web_public_visitor", () => {
    page_params.is_web_public_visitor = true;
    activity.send_presence_to_server();
});
