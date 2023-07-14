"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, with_overrides, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");
const {page_params, user_settings} = require("./lib/zpage_params");

const $window_stub = $.create("window-stub");
set_global("to_$", () => $window_stub);
$(window).idle = () => {};

const _document = {
    hasFocus() {
        return true;
    },
};

const channel = mock_esm("../src/channel");
const compose_state = mock_esm("../src/compose_state");
const narrow = mock_esm("../src/narrow");
const padded_widget = mock_esm("../src/padded_widget");
const pm_list = mock_esm("../src/pm_list");
const popovers = mock_esm("../src/popovers");
const resize = mock_esm("../src/resize");
const scroll_util = mock_esm("../src/scroll_util");
const watchdog = mock_esm("../src/watchdog");

set_global("document", _document);

const huddle_data = zrequire("huddle_data");
const compose_fade = zrequire("compose_fade");
const keydown_util = zrequire("keydown_util");
const muted_users = zrequire("muted_users");
const presence = zrequire("presence");
const people = zrequire("people");
const buddy_data = zrequire("buddy_data");
const {buddy_list} = zrequire("buddy_list");
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

function clear_buddy_list() {
    buddy_list.populate({
        keys: [],
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

        presence.presence_info.set(alice.user_id, {status: "active"});
        presence.presence_info.set(fred.user_id, {status: "active"});
        presence.presence_info.set(jill.user_id, {status: "active"});
        presence.presence_info.set(mark.user_id, {status: "idle"});
        presence.presence_info.set(norbert.user_id, {status: "active"});
        presence.presence_info.set(zoe.user_id, {status: "active"});
        presence.presence_info.set(me.user_id, {status: "active"});

        clear_buddy_list();
        muted_users.set_muted_users([]);

        activity.clear_for_testing();
        activity.set_cursor_and_filter();

        f(helpers);

        presence.clear_internal_data();
    });
}

run_test("reload_defaults", () => {
    activity.clear_for_testing();
    blueslip.expect("warn", "get_filter_text() is called before initialization");
    assert.equal(activity.get_filter_text(), "");
});

test("get_status", () => {
    page_params.realm_users = [];
    page_params.user_id = 999;

    assert.equal(presence.get_status(page_params.user_id), "active");
    assert.equal(presence.get_status(alice.user_id), "active");
    assert.equal(presence.get_status(mark.user_id), "idle");
    assert.equal(presence.get_status(fred.user_id), "active");

    user_settings.presence_enabled = false;
    assert.equal(presence.get_status(page_params.user_id), "offline");
    user_settings.presence_enabled = true;
    assert.equal(presence.get_status(page_params.user_id), "active");

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
    override(padded_widget, "update_padding", () => {});
    mock_template("presence_rows.hbs", false, (data) => {
        assert.equal(data.presence_rows.length, 7);
        assert.equal(data.presence_rows[0].user_id, me.user_id);
    });

    $(".user-list-filter").trigger("focus");
    compose_state.private_message_recipient = () => fred.email;
    compose_fade.set_focused_recipient("private");

    const user_ids = activity.build_user_sidebar();

    assert.deepEqual(user_ids, [
        me.user_id,
        alice.user_id,
        fred.user_id,
        jill.user_id,
        norbert.user_id,
        zoe.user_id,
        mark.user_id,
    ]);
});

function simulate_right_column_buddy_list() {
    $(".user-list-filter").closest = (selector) => {
        assert.equal(selector, ".app-main [class^='column-']");
        return $.create("right-sidebar").addClass("column-right");
    };
}

function buddy_list_add(user_id, $stub) {
    if ($stub.attr) {
        $stub.attr("data-user-id", user_id);
    }
    $stub.length = 1;
    const sel = `li.user_sidebar_entry[data-user-id='${CSS.escape(user_id)}']`;
    $("#user_presences").set_find_results(sel, $stub);
}

test("direct_message_update_dom_counts", () => {
    const $count = $.create("alice-unread-count");
    const pm_key = alice.user_id.toString();
    const $li = $.create("alice stub");
    buddy_list_add(pm_key, $li);
    $li.set_find_results(".unread_count", $count);
    $count.set_parents_result("li", $li);

    const counts = new Map();
    counts.set(pm_key, 5);
    $li.addClass("user_sidebar_entry");

    activity.update_dom_with_unread_counts({pm_count: counts});
    assert.equal($count.text(), "5");

    counts.set(pm_key, 0);

    activity.update_dom_with_unread_counts({pm_count: counts});
    assert.equal($count.text(), "");
});

test("handlers", ({override, mock_template}) => {
    let filter_key_handlers;

    mock_template("presence_rows.hbs", false, () => {});

    override(keydown_util, "handle", (opts) => {
        filter_key_handlers = opts.handlers;
    });
    override(scroll_util, "scroll_element_into_container", () => {});
    override(padded_widget, "update_padding", () => {});
    override(popovers, "hide_all", () => {});
    override(popovers, "hide_all_except_sidebars", () => {});
    override(popovers, "show_userlist_sidebar", () => {});
    override(resize, "resize_sidebars", () => {});

    // This is kind of weak coverage; we are mostly making sure that
    // keys and clicks got mapped to functions that don't crash.
    let $me_li;
    let $alice_li;
    let $fred_li;

    let narrowed;

    override(narrow, "by", (_method, email) => {
        assert.equal(email, "alice@zulip.com");
        narrowed = true;
    });

    function init() {
        $.clear_all_elements();
        buddy_list.populate({
            keys: [me.user_id, alice.user_id, fred.user_id],
        });
        activity.set_cursor_and_filter();
        $("#user_presences").empty = () => {};

        $me_li = $.create("me stub");
        $alice_li = $.create("alice stub");
        $fred_li = $.create("fred stub");

        buddy_list_add(me.user_id, $me_li);
        buddy_list_add(alice.user_id, $alice_li);
        buddy_list_add(fred.user_id, $fred_li);
    }

    (function test_filter_keys() {
        init();
        activity.user_cursor.go_to(alice.user_id);
        filter_key_handlers.ArrowDown();
        filter_key_handlers.ArrowUp();
    })();

    (function test_click_filter() {
        init();
        const e = {
            stopPropagation() {},
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
        filter_key_handlers.Enter();
        assert.ok(narrowed);

        // get line coverage for cleared case
        activity.user_cursor.clear();
        filter_key_handlers.Enter();
    })();

    (function test_click_handler() {
        init();
        // We wire up the click handler in click_handlers.js,
        // so this just tests the called function.
        narrowed = false;
        activity.narrow_for_user({$li: $alice_li});
        assert.ok(narrowed);
    })();

    (function test_blur_filter() {
        init();
        const e = {};
        const handler = $(".user-list-filter").get_on_handler("blur");
        handler(e);
    })();
});

test("first/prev/next", ({override, mock_template}) => {
    let rendered_alice;
    let rendered_fred;
    user_settings.user_list_style = 2;

    mock_template("presence_row.hbs", false, (data) => {
        switch (data.user_id) {
            case alice.user_id:
                rendered_alice = true;
                assert.deepEqual(data, {
                    faded: true,
                    href: "#narrow/dm/1-Alice-Smith",
                    is_current_user: false,
                    name: "Alice Smith",
                    num_unread: 0,
                    user_circle_class: "user_circle_green",
                    user_id: alice.user_id,
                    status_emoji_info: undefined,
                    status_text: undefined,
                    user_list_style: {
                        COMPACT: false,
                        WITH_STATUS: true,
                        WITH_AVATAR: false,
                    },
                });
                break;
            case fred.user_id:
                rendered_fred = true;
                assert.deepEqual(data, {
                    href: "#narrow/dm/2-Fred-Flintstone",
                    name: "Fred Flintstone",
                    user_id: fred.user_id,
                    is_current_user: false,
                    num_unread: 0,
                    user_circle_class: "user_circle_green",
                    faded: false,
                    status_emoji_info: undefined,
                    status_text: undefined,
                    user_list_style: {
                        COMPACT: false,
                        WITH_STATUS: true,
                        WITH_AVATAR: false,
                    },
                });
                break;
            /* istanbul ignore next */
            default:
                throw new Error(`we did not expect to have to render a row for  ${data.name}`);
        }
    });

    override(padded_widget, "update_padding", () => {});

    assert.equal(buddy_list.first_key(), undefined);
    assert.equal(buddy_list.prev_key(alice.user_id), undefined);
    assert.equal(buddy_list.next_key(alice.user_id), undefined);

    override(buddy_list.$container, "append", () => {});

    activity.redraw_user(alice.user_id);
    activity.redraw_user(fred.user_id);

    assert.equal(buddy_list.first_key(), alice.user_id);
    assert.equal(buddy_list.prev_key(alice.user_id), undefined);
    assert.equal(buddy_list.prev_key(fred.user_id), alice.user_id);

    assert.equal(buddy_list.next_key(alice.user_id), fred.user_id);
    assert.equal(buddy_list.next_key(fred.user_id), undefined);

    assert.ok(rendered_alice);
    assert.ok(rendered_fred);
});

test("insert_one_user_into_empty_list", ({override, mock_template}) => {
    user_settings.user_list_style = 2;
    mock_template("presence_row.hbs", true, (data, html) => {
        assert.deepEqual(data, {
            href: "#narrow/dm/1-Alice-Smith",
            name: "Alice Smith",
            user_id: 1,
            is_current_user: false,
            num_unread: 0,
            user_circle_class: "user_circle_green",
            faded: true,
            status_emoji_info: undefined,
            status_text: undefined,
            user_list_style: {
                COMPACT: false,
                WITH_STATUS: true,
                WITH_AVATAR: false,
            },
        });
        assert.ok(html.startsWith("<li data-user-id="));
        return html;
    });

    override(padded_widget, "update_padding", () => {});

    let appended_html;
    override(buddy_list.$container, "append", (html) => {
        appended_html = html;
    });

    activity.redraw_user(alice.user_id);
    assert.ok(appended_html.indexOf('data-user-id="1"') > 0);
    assert.ok(appended_html.indexOf("user_circle_green") > 0);
});

test("insert_alice_then_fred", ({override, mock_template}) => {
    mock_template("presence_row.hbs", true, (_data, html) => html);

    let appended_html;
    override(buddy_list.$container, "append", (html) => {
        appended_html = html;
    });
    override(padded_widget, "update_padding", () => {});

    activity.redraw_user(alice.user_id);
    assert.ok(appended_html.indexOf('data-user-id="1"') > 0);
    assert.ok(appended_html.indexOf("user_circle_green") > 0);

    activity.redraw_user(fred.user_id);
    assert.ok(appended_html.indexOf('data-user-id="2"') > 0);
    assert.ok(appended_html.indexOf("user_circle_green") > 0);
});

test("insert_fred_then_alice_then_rename", ({override, mock_template}) => {
    mock_template("presence_row.hbs", true, (_data, html) => html);

    let appended_html;
    override(buddy_list.$container, "append", (html) => {
        appended_html = html;
    });
    override(padded_widget, "update_padding", () => {});

    activity.redraw_user(fred.user_id);
    assert.ok(appended_html.indexOf('data-user-id="2"') > 0);
    assert.ok(appended_html.indexOf("user_circle_green") > 0);

    const $fred_stub = $.create("fred-first");
    buddy_list_add(fred.user_id, $fred_stub);

    let inserted_html;
    $fred_stub.before = (html) => {
        inserted_html = html;
    };

    let fred_removed;
    $fred_stub.remove = () => {
        fred_removed = true;
    };

    activity.redraw_user(alice.user_id);
    assert.ok(inserted_html.indexOf('data-user-id="1"') > 0);
    assert.ok(inserted_html.indexOf("user_circle_green") > 0);

    // Next rename fred to Aaron.
    const fred_with_new_name = {
        email: fred.email,
        user_id: fred.user_id,
        full_name: "Aaron",
    };
    people.add_active_user(fred_with_new_name);

    const $alice_stub = $.create("alice-first");
    buddy_list_add(alice.user_id, $alice_stub);

    $alice_stub.before = (html) => {
        inserted_html = html;
    };

    activity.redraw_user(fred_with_new_name.user_id);
    assert.ok(fred_removed);
    assert.ok(appended_html.indexOf('data-user-id="2"') > 0);

    // restore old Fred data
    people.add_active_user(fred);
});

test("insert_unfiltered_user_with_filter", () => {
    // This test only tests that we do not explode when
    // try to insert Fred into a list where he does not
    // match the search filter.
    const $user_filter = $(".user-list-filter");
    $user_filter.val("do-not-match-filter");
    activity.redraw_user(fred.user_id);
});

test("realm_presence_disabled", () => {
    page_params.realm_presence_disabled = true;

    activity.redraw_user();
    activity.build_user_sidebar();
});

test("redraw_muted_user", () => {
    muted_users.add_muted_user(mark.user_id);
    activity.redraw_user(mark.user_id);
    assert.equal($("#user_presences").html(), "never-been-set");
});

test("update_presence_info", ({override}) => {
    override(pm_list, "update_private_messages", () => {});

    page_params.realm_presence_disabled = false;
    page_params.server_presence_ping_interval_seconds = 60;
    page_params.server_presence_offline_threshold_seconds = 200;

    const server_time = 500;
    const info = {
        website: {
            status: "active",
            timestamp: server_time,
        },
    };

    const $alice_li = $.create("alice stub");
    buddy_list_add(alice.user_id, $alice_li);

    let inserted;
    override(buddy_list, "insert_or_move", () => {
        inserted = true;
    });

    presence.presence_info.delete(me.user_id);
    activity.update_presence_info(me.user_id, info, server_time);
    assert.ok(inserted);
    assert.deepEqual(presence.presence_info.get(me.user_id).status, "active");

    presence.presence_info.delete(alice.user_id);
    activity.update_presence_info(alice.user_id, info, server_time);
    assert.ok(inserted);

    const expected = {status: "active", last_active: 500};
    assert.deepEqual(presence.presence_info.get(alice.user_id), expected);
});

test("initialize", ({override, mock_template}) => {
    mock_template("presence_rows.hbs", false, () => {});
    override(padded_widget, "update_padding", () => {});
    override(pm_list, "update_private_messages", () => {});
    override(watchdog, "check_for_unsuspend", () => {});

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
        buddy_list.$container = $("#user_presences");
        buddy_list.$container.append = () => {};
        clear_buddy_list();
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
    payload.success({
        zephyr_mirror_active: true,
        presences: {},
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
    payload.success({
        zephyr_mirror_active: false,
        presences: {},
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
    override_rewire(activity, "send_presence_to_server", () => {});

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
