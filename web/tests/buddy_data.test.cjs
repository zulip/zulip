"use strict";

const assert = require("node:assert/strict");

const _ = require("lodash");

const {make_message_list} = require("./lib/message_list.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {noop, run_test} = require("./lib/test.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => true,
});
const timerender = mock_esm("../src/timerender");
mock_esm("../src/buddy_list", {
    buddy_list: {
        rerender_participants: noop,
    },
});

const compose_fade_helper = zrequire("compose_fade_helper");
const activity_ui = zrequire("activity_ui");
const muted_users = zrequire("muted_users");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const presence = zrequire("presence");
const stream_data = zrequire("stream_data");
const user_status = zrequire("user_status");
const buddy_data = zrequire("buddy_data");
const message_lists = zrequire("message_lists");
const {set_current_user, set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");

const realm = {};
set_realm(realm);
const current_user = {};
set_current_user(current_user);
const user_settings = {};
initialize_user_settings({user_settings});

// The buddy_data module is mostly tested indirectly through
// activity.test.cjs, but we should feel free to add direct tests
// here.

const selma = {
    user_id: 1000,
    full_name: "Human Selma",
    email: "selma@example.com",
};

const me = {
    user_id: 1001,
    full_name: "Human Myself",
    email: "self@example.com",
};

const alice = {
    email: "alice@zulip.com",
    user_id: 1002,
    full_name: "Alice Smith",
};

const fred = {
    email: "fred@zulip.com",
    user_id: 1003,
    full_name: "Fred Flintstone",
};

const jill = {
    email: "jill@zulip.com",
    user_id: 1004,
    full_name: "Jill Hill",
};

const mark = {
    email: "mark@zulip.com",
    user_id: 1005,
    full_name: "Marky Mark",
};

const old_user = {
    user_id: 9999,
    full_name: "Old User",
    email: "old_user@example.com",
};

const bot = {
    user_id: 55555,
    full_name: "Red Herring Bot",
    email: "bot@example.com",
    is_bot: true,
    bot_owner_id: null,
};

const bot_with_owner = {
    user_id: 55556,
    full_name: "Blue Herring Bot",
    email: "bot_with_owner@example.com",
    is_bot: true,
    bot_owner_id: 1001,
    bot_owner_full_name: "Human Myself",
};

function add_canned_users() {
    people.add_active_user(alice);
    people.add_active_user(bot);
    people.add_active_user(bot_with_owner);
    people.add_active_user(fred);
    people.add_active_user(jill);
    people.add_active_user(mark);
    people.add_active_user(old_user);
    people.add_active_user(selma);
}

function test(label, f) {
    run_test(label, (helpers) => {
        helpers.override(user_settings, "presence_enabled", true);
        compose_fade_helper.clear_focused_recipient();
        stream_data.clear_subscriptions();
        peer_data.clear_for_testing();
        user_status.initialize({user_status: {}});
        presence.presence_info.clear();
        people.init();
        people.add_active_user(me);
        people.initialize_current_user(me.user_id);
        muted_users.set_muted_users([]);
        message_lists.set_current(undefined);

        f(helpers);

        presence.clear_internal_data();
    });
}

function set_presence(user_id, status) {
    presence.presence_info.set(user_id, {
        status,
        last_active: 9999,
    });
}

test("user_circle, level", ({override}) => {
    add_canned_users();

    set_presence(selma.user_id, "active");
    assert.equal(buddy_data.get_user_circle_class(selma.user_id), "user-circle-active");
    assert.equal(buddy_data.level(selma.user_id), 1);

    set_presence(selma.user_id, "idle");
    assert.equal(buddy_data.get_user_circle_class(selma.user_id), "user-circle-idle");
    assert.equal(buddy_data.level(selma.user_id), 2);

    set_presence(selma.user_id, "offline");
    assert.equal(buddy_data.get_user_circle_class(selma.user_id), "user-circle-offline");
    assert.equal(buddy_data.level(selma.user_id), 3);

    set_presence(me.user_id, "active");
    assert.equal(buddy_data.get_user_circle_class(me.user_id), "user-circle-active");
    assert.equal(buddy_data.level(me.user_id), 0);

    override(user_settings, "presence_enabled", false);
    assert.equal(buddy_data.get_user_circle_class(me.user_id), "user-circle-offline");
    assert.equal(buddy_data.level(me.user_id), 0);

    override(user_settings, "presence_enabled", true);
    assert.equal(buddy_data.get_user_circle_class(me.user_id), "user-circle-active");
    assert.equal(buddy_data.level(me.user_id), 0);

    set_presence(fred.user_id, "idle");
    assert.equal(buddy_data.get_user_circle_class(fred.user_id), "user-circle-idle");
    assert.equal(buddy_data.level(fred.user_id), 2);

    set_presence(fred.user_id, undefined);
    assert.equal(buddy_data.get_user_circle_class(fred.user_id), "user-circle-offline");
    assert.equal(buddy_data.level(fred.user_id), 3);

    set_presence(fred.user_id, undefined);
    assert.equal(buddy_data.get_user_circle_class(fred.user_id, true), "user-circle-deactivated");
    assert.equal(buddy_data.level(fred.user_id), 3);
});

test("title_data", ({override}) => {
    page_params.presence_history_limit_days_for_web_app = 365;
    add_canned_users();

    // Groups
    let is_group = true;
    const user_ids_string = "9999,1000";
    let expected_group_data = {
        first_line: "Human Selma and Old User",
        second_line: "",
        third_line: "",
    };
    assert.deepEqual(buddy_data.get_title_data(user_ids_string, is_group), expected_group_data);

    is_group = "";

    // Bots with owners.
    expected_group_data = {
        first_line: "Blue Herring Bot",
        second_line: "translated: Owner: Human Myself",
        third_line: "",
        is_deactivated: false,
    };
    assert.deepEqual(
        buddy_data.get_title_data(bot_with_owner.user_id, is_group),
        expected_group_data,
    );

    // Bots without owners.
    expected_group_data = {
        first_line: "Red Herring Bot",
        second_line: "",
        third_line: "",
    };
    assert.deepEqual(buddy_data.get_title_data(bot.user_id, is_group), expected_group_data);

    // Individual users.
    user_status.set_status_text({
        user_id: me.user_id,
        status_text: "out to lunch",
    });

    let expected_data = {
        first_line: "Human Myself",
        second_line: "out to lunch",
        third_line: "translated: Active now",
        show_you: true,
    };
    override(current_user, "user_id", me.user_id);
    assert.deepEqual(buddy_data.get_title_data(me.user_id, is_group), expected_data);

    expected_data = {
        first_line: "Old User",
        second_line: "translated: Not active in the last year",
        third_line: "",
        show_you: false,
    };
    assert.deepEqual(buddy_data.get_title_data(old_user.user_id, is_group), expected_data);

    // Deactivated users.
    people.deactivate(selma);
    expected_data = {
        first_line: "Human Selma",
        second_line: "translated: This user has been deactivated.",
        third_line: "",
        show_you: false,
        is_deactivated: true,
    };
    assert.deepEqual(buddy_data.get_title_data(selma.user_id, is_group), expected_data);

    // Deactivated bots.
    people.deactivate(bot_with_owner);
    expected_group_data = {
        first_line: "Blue Herring Bot",
        second_line: "translated: Owner: Human Myself",
        third_line: "translated: This bot has been deactivated.",
        is_deactivated: true,
    };
    assert.deepEqual(
        buddy_data.get_title_data(bot_with_owner.user_id, is_group),
        expected_group_data,
    );
});

test("filters deactivated users", () => {
    add_canned_users();

    set_presence(selma.user_id, "active");
    set_presence(me.user_id, "active");

    let user_ids = buddy_data.get_filtered_and_sorted_user_ids("selm");

    assert.deepEqual(user_ids, [selma.user_id]);
    assert.ok(buddy_data.matches_filter("selm", selma.user_id));

    // Deactivated users are excluded.
    people.deactivate(selma);

    user_ids = buddy_data.get_filtered_and_sorted_user_ids("selm");
    assert.deepEqual(user_ids, []);

    user_ids = buddy_data.get_filtered_and_sorted_user_ids();
    assert.equal(user_ids.includes(selma.user_id), false);
    assert.ok(!buddy_data.matches_filter("selm", selma.user_id));
});

test("muted users excluded from search", () => {
    people.add_active_user(selma);
    muted_users.add_muted_user(selma.user_id);

    let user_ids = buddy_data.get_filtered_and_sorted_user_ids();
    assert.equal(user_ids.includes(selma.user_id), false);
    user_ids = buddy_data.get_filtered_and_sorted_user_ids("selm");
    assert.deepEqual(user_ids, []);
    assert.ok(!buddy_data.matches_filter("selm", selma.user_id));

    muted_users.remove_muted_user(selma.user_id);
    user_ids = buddy_data.get_filtered_and_sorted_user_ids("selm");
    assert.deepEqual(user_ids, [selma.user_id]);
    assert.ok(buddy_data.matches_filter("selm", selma.user_id));
});

test("bulk_data_hacks", ({override_rewire}) => {
    // sanity check
    assert.equal(mark.user_id, 1005);

    for (const i of _.range(mark.user_id + 1, 2000)) {
        const person = {
            user_id: i,
            full_name: `Human ${i}`,
            email: `person${i}@example.com`,
        };
        people.add_active_user(person);
    }
    add_canned_users();

    // Make 400 of the users active
    set_presence(selma.user_id, "active");
    set_presence(me.user_id, "active");

    for (const user_id of _.range(1000, 1400)) {
        set_presence(user_id, "active");
    }

    // And then 300 not active
    for (const user_id of _.range(1400, 1700)) {
        set_presence(user_id, "offline");
    }

    let user_ids;

    // Even though we have 1000 users, we only get the 400 active
    // users.  This is a consequence of buddy_data.maybe_shrink_list.
    user_ids = buddy_data.get_filtered_and_sorted_user_ids();
    assert.equal(user_ids.length, 400);

    user_ids = buddy_data.get_filtered_and_sorted_user_ids("");
    assert.equal(user_ids.length, 400);

    // We don't match on "so", because it's not at the start of a
    // word in the name/email.
    user_ids = buddy_data.get_filtered_and_sorted_user_ids("so");
    assert.equal(user_ids.length, 0);

    // We match on "h" for the first name, and the result limit
    // is relaxed for searches.
    user_ids = buddy_data.get_filtered_and_sorted_user_ids("h");
    assert.equal(user_ids.length, 997);

    // We match on "p" for the email.
    user_ids = buddy_data.get_filtered_and_sorted_user_ids("p");
    assert.equal(user_ids.length, 994);

    // Make our shrink limit higher, and go back to an empty search.
    // We won't get all 1000 users, just the present ones.
    override_rewire(buddy_data, "max_size_before_shrinking", 50000);
    user_ids = buddy_data.get_filtered_and_sorted_user_ids("");
    assert.equal(user_ids.length, 700);
});

test("always show me", () => {
    assert.deepEqual(buddy_data.get_filtered_and_sorted_user_ids(""), [me.user_id]);

    // try to make us show twice
    presence.presence_info.set(me.user_id, {status: "active"});
    assert.deepEqual(buddy_data.get_filtered_and_sorted_user_ids(""), [me.user_id]);
});

test("always show pm users", () => {
    people.add_active_user(selma);
    message_lists.set_current(make_message_list([{operator: "dm", operand: selma.email}]));

    assert.deepEqual(buddy_data.get_filtered_and_sorted_user_ids(""), [me.user_id, selma.user_id]);
});

test("show offline channel subscribers for small channels", ({override_rewire}) => {
    // Add a bunch of users to hit max_size_before_shrinking, which will hide some
    // offline users.
    for (const i of _.range(2000, 2700)) {
        const person = {
            user_id: i,
            full_name: `Human ${i}`,
            email: `person${i}@example.com`,
        };
        people.add_active_user(person);
    }
    for (const user_id of _.range(2000, 2700)) {
        set_presence(user_id, "offline");
    }

    people.add_active_user(alice);
    set_presence(alice.user_id, "active");
    people.add_active_user(fred);
    set_presence(fred.user_id, "offline");
    people.add_active_user(selma);
    set_presence(selma.user_id, "offline");
    people.add_active_user(jill);
    set_presence(jill.user_id, "offline");

    const stream_id = 1001;
    const sub = {name: "Rome", subscribed: true, stream_id};
    stream_data.add_sub(sub);
    peer_data.set_subscribers(stream_id, [
        selma.user_id,
        alice.user_id,
        fred.user_id,
        jill.user_id,
        me.user_id,
    ]);

    const filter_terms = [
        {operator: "channel", operand: sub.stream_id},
        {operator: "topic", operand: "Foo"},
    ];
    message_lists.set_current(make_message_list(filter_terms));
    assert.deepEqual(buddy_data.get_filtered_and_sorted_user_ids(""), [
        me.user_id,
        alice.user_id,
        fred.user_id,
        selma.user_id,
        jill.user_id,
    ]);

    // Make the max channel size lower, so that we hide the offline users
    override_rewire(buddy_data, "max_channel_size_to_show_all_subscribers", 2);
    assert.deepEqual(buddy_data.get_filtered_and_sorted_user_ids(""), [me.user_id, alice.user_id]);
});

test("get_conversation_participants", () => {
    people.add_active_user(selma);

    const rome_sub = {name: "Rome", subscribed: true, stream_id: 1001};
    stream_data.add_sub(rome_sub);
    peer_data.set_subscribers(rome_sub.stream_id, [selma.user_id, me.user_id]);

    const filter_terms = [
        {operator: "channel", operand: rome_sub.stream_id},
        {operator: "topic", operand: "Foo"},
    ];
    message_lists.set_current(
        make_message_list(filter_terms, {
            visible_participants: [selma.user_id],
        }),
    );

    activity_ui.rerender_user_sidebar_participants();
    assert.deepEqual(
        buddy_data.get_conversation_participants_callback()(),
        new Set([selma.user_id]),
    );
});

test("level", ({override}) => {
    override(realm, "server_presence_offline_threshold_seconds", 200);

    add_canned_users();
    assert.equal(buddy_data.level(me.user_id), 0);
    assert.equal(buddy_data.level(selma.user_id), 3);

    const server_time = 9999;
    const info = {
        website: {
            status: "active",
            timestamp: server_time,
        },
    };
    presence.update_info_from_event(me.user_id, info, server_time);
    presence.update_info_from_event(selma.user_id, info, server_time);

    assert.equal(buddy_data.level(me.user_id), 0);
    assert.equal(buddy_data.level(selma.user_id), 1);

    override(user_settings, "presence_enabled", false);
    set_presence(selma.user_id, "offline");

    // Selma gets demoted to level 3, but "me"
    // stays in level 0.
    assert.equal(buddy_data.level(me.user_id), 0);
    assert.equal(buddy_data.level(selma.user_id), 3);
});

test("compare_function", () => {
    const first_user_shown_higher = -1;
    const second_user_shown_higher = 1;

    const stream_id = 1001;
    const sub = {name: "Rome", subscribed: true, stream_id};
    stream_data.add_sub(sub);
    people.add_active_user(alice);
    people.add_active_user(fred);

    // Alice is higher because of alphabetical sorting.
    peer_data.set_subscribers(stream_id, []);
    assert.equal(
        second_user_shown_higher,
        buddy_data.compare_function(fred.user_id, alice.user_id, stream_id, new Set(), new Set()),
    );

    // Fred is higher because they're in the narrow and Alice isn't.
    peer_data.set_subscribers(stream_id, [fred.user_id]);
    assert.equal(
        first_user_shown_higher,
        buddy_data.compare_function(fred.user_id, alice.user_id, stream_id, new Set(), new Set()),
    );
    assert.equal(
        second_user_shown_higher,
        buddy_data.compare_function(alice.user_id, fred.user_id, stream_id, new Set(), new Set()),
    );

    // Fred is higher because they're in the DM conversation and Alice isn't.
    assert.equal(
        first_user_shown_higher,
        buddy_data.compare_function(
            fred.user_id,
            alice.user_id,
            undefined,
            new Set([fred.user_id]),
            new Set(),
        ),
    );

    // Fred is higher because they're in the conversation and Alice isn't.
    assert.equal(
        first_user_shown_higher,
        buddy_data.compare_function(
            fred.user_id,
            alice.user_id,
            undefined,
            new Set(),
            new Set([fred.user_id]),
        ),
    );

    assert.equal(
        second_user_shown_higher,
        buddy_data.compare_function(
            alice.user_id,
            fred.user_id,
            undefined,
            new Set(),
            new Set([fred.user_id]),
        ),
    );

    // Alice is higher because of alphabetical sorting.
    assert.equal(
        second_user_shown_higher,
        buddy_data.compare_function(fred.user_id, alice.user_id, undefined, new Set(), new Set()),
    );

    // The user is part of a DM conversation, though that's not explicitly in the DM list.
    assert.equal(
        first_user_shown_higher,
        buddy_data.compare_function(
            me.user_id,
            alice.user_id,
            undefined,
            new Set([fred.user_id]),
            new Set(),
        ),
    );
});

test("user_last_seen_time_status", ({override}) => {
    page_params.presence_history_limit_days_for_web_app = 365;
    set_presence(selma.user_id, "active");
    set_presence(me.user_id, "active");

    assert.equal(buddy_data.user_last_seen_time_status(selma.user_id), "translated: Active now");

    override(realm, "realm_is_zephyr_mirror_realm", true);
    assert.equal(
        buddy_data.user_last_seen_time_status(old_user.user_id),
        "translated: Activity unknown",
    );
    override(realm, "realm_is_zephyr_mirror_realm", false);
    assert.equal(
        buddy_data.user_last_seen_time_status(old_user.user_id),
        "translated: Not active in the last year",
    );

    presence.presence_info.set(old_user.user_id, {last_active: 1526137743});

    override(timerender, "last_seen_status_from_date", (date) => {
        assert.deepEqual(date, new Date(1526137743000));
        return "translated: Active May 12";
    });

    assert.equal(
        buddy_data.user_last_seen_time_status(old_user.user_id),
        "translated: Active May 12",
    );

    set_presence(selma.user_id, "idle");
    assert.equal(buddy_data.user_last_seen_time_status(selma.user_id), "translated: Idle");

    presence.presence_info.set(old_user.user_id, {last_active: undefined});
    const missing_callback = (user_id) => {
        assert.equal(user_id, old_user.user_id);
    };
    assert.equal(buddy_data.user_last_seen_time_status(old_user.user_id, missing_callback), "");
});

test("get_items_for_users", ({override}) => {
    people.add_active_user(alice);
    people.add_active_user(fred);
    set_presence(alice.user_id, "offline");
    override(user_settings, "emojiset", "google");
    override(user_settings, "user_list_style", 2);

    const status_emoji_info = {
        emoji_alt_code: false,
        emoji_name: "car",
        emoji_code: "1f697",
        reaction_type: "unicode_emoji",
    };

    const status_emoji_info_event = {
        id: 1,
        type: "user_status",
        status_text: "",
        ...status_emoji_info,
    };

    const user_ids = [me.user_id, alice.user_id, fred.user_id];
    for (const user_id of user_ids) {
        user_status.set_status_emoji({user_id, ...status_emoji_info_event});
    }

    const user_list_style = {
        COMPACT: false,
        WITH_STATUS: true,
        WITH_AVATAR: false,
    };

    assert.deepEqual(buddy_data.get_items_for_users(user_ids), [
        {
            href: "#narrow/dm/1001-Human-Myself",
            is_current_user: true,
            name: "Human Myself",
            num_unread: 0,
            profile_picture: "/avatar/1001",
            status_emoji_info,
            status_text: undefined,
            has_status_text: false,
            user_circle_class: "user-circle-active",
            user_id: 1001,
            user_list_style,
            should_add_guest_user_indicator: false,
        },
        {
            href: "#narrow/dm/1002-Alice-Smith",
            is_current_user: false,
            name: "Alice Smith",
            num_unread: 0,
            profile_picture: "/avatar/1002",
            status_emoji_info,
            status_text: undefined,
            has_status_text: false,
            user_circle_class: "user-circle-offline",
            user_id: 1002,
            user_list_style,
            should_add_guest_user_indicator: false,
        },
        {
            href: "#narrow/dm/1003-Fred-Flintstone",
            is_current_user: false,
            name: "Fred Flintstone",
            num_unread: 0,
            profile_picture: "/avatar/1003",
            status_emoji_info,
            status_text: undefined,
            has_status_text: false,
            user_circle_class: "user-circle-offline",
            user_id: 1003,
            user_list_style,
            should_add_guest_user_indicator: false,
        },
    ]);
});

test("unknown user id in presence", () => {
    // This test is to make sure that we don't generate errors
    // when we have a user_id in presence that we don't have
    // information about.
    // Such scenarios can happen if we receive presence info involving
    // a new user before the user creation event reaches us.
    presence.presence_info.set(999, {status: "active"});
    const user_ids = buddy_data.get_filtered_and_sorted_user_ids();

    // This user id should not be present in the filtered list,
    // it's meant to be ignored until we know about the user.
    assert.equal(user_ids.includes(999), false);
});
