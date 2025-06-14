"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const settings_config = zrequire("settings_config");
const pm_conversations = zrequire("pm_conversations");

const bootstrap_typeahead = zrequire("bootstrap_typeahead");
const recent_senders = zrequire("recent_senders");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const stream_list_sort = zrequire("stream_list_sort");
const compose_state = zrequire("compose_state");
const emoji = zrequire("emoji");
const pygments_data = zrequire("pygments_data");
const {set_current_user, set_realm} = zrequire("state_data");
const util = zrequire("util");
const ct = zrequire("composebox_typeahead");
const th = zrequire("typeahead_helper");
const user_groups = zrequire("user_groups");
const {initialize_user_settings} = zrequire("user_settings");

mock_esm("../src/channel", {
    get: () => ({subscribers: []}),
});

const current_user = {};
set_current_user(current_user);
const realm = {};
set_realm(realm);
const user_settings = {};
initialize_user_settings({user_settings});

let next_id = 0;

function assertSameEmails(lst1, lst2) {
    assert.deepEqual(
        lst1.map((r) => r.user.email),
        lst2.map((r) => r.user.email),
    );
}

function user_item(user) {
    return {type: "user", user};
}

function broadcast_item(user) {
    return {type: "broadcast", user};
}

function user_group_item(user_group) {
    return {type: "user_group", ...user_group};
}

const a_bot = {
    email: "a_bot@zulip.com",
    full_name: "A Zulip test bot",
    is_admin: false,
    is_bot: true,
    user_id: 1,
};
const a_bot_item = user_item(a_bot);

const a_user = {
    email: "a_user@zulip.org",
    full_name: "A Zulip user",
    is_admin: false,
    is_bot: false,
    user_id: 2,
};
const a_user_item = user_item(a_user);

const b_user_1 = {
    email: "b_user_1@zulip.net",
    full_name: "Bob 1",
    is_admin: false,
    is_bot: false,
    user_id: 3,
};
const b_user_1_item = user_item(b_user_1);

const b_user_2 = {
    email: "b_user_2@zulip.net",
    full_name: "Bob 2",
    is_admin: true,
    is_bot: false,
    user_id: 4,
};
const b_user_2_item = user_item(b_user_2);

const b_user_3 = {
    email: "b_user_3@zulip.net",
    full_name: "Bob 3",
    is_admin: false,
    is_bot: false,
    user_id: 5,
};
const b_user_3_item = user_item(b_user_3);

const b_bot = {
    email: "b_bot@example.com",
    full_name: "B bot",
    is_admin: false,
    is_bot: true,
    user_id: 6,
};
const b_bot_item = user_item(b_bot);

const zman = {
    email: "zman@test.net",
    full_name: "Zman",
    is_admin: false,
    is_bot: false,
    user_id: 7,
};
const zman_item = user_item(zman);

const matches = [a_bot, a_user, b_user_1, b_user_2, b_user_3, b_bot, zman];

for (const person of matches) {
    people.add_active_user(person);
}

const dev_sub = {
    name: "Dev",
    color: "blue",
    stream_id: 1,
};

const linux_sub = {
    name: "Linux",
    color: "red",
    stream_id: 2,
};
stream_data.create_streams([dev_sub, linux_sub]);
stream_data.add_sub(dev_sub);
stream_data.add_sub(linux_sub);

const bob_system_group = {
    id: 1,
    name: "Bob system group",
    description: "",
    members: new Set([]),
    is_system_group: true,
};
const bob_system_group_item = user_group_item(bob_system_group);

const bob_group = {
    id: 2,
    name: "Bob group",
    description: "",
    members: new Set([]),
    is_system_group: false,
};
const bob_group_item = user_group_item(bob_group);

const second_bob_group = {
    id: 3,
    name: "bob 2 group",
    description: "",
    members: new Set([b_user_2.user_id]),
    is_system_group: false,
};

const admins_group = {
    id: 4,
    name: "Admins of zulip",
    description: "",
    members: new Set([]),
    is_system_group: false,
};
const admins_group_item = user_group_item(admins_group);

const members_group = {
    id: 5,
    name: "role:members",
    description: "",
    members: new Set([]),
    is_system_group: true,
};
const members_group_item = user_group_item(members_group);

const everyone_group = {
    id: 6,
    name: "role:everyone",
    description: "",
    members: new Set([]),
    is_system_group: true,
};

user_groups.initialize({
    realm_user_groups: [
        bob_system_group,
        bob_group,
        second_bob_group,
        admins_group,
        members_group,
        everyone_group,
    ],
});

function test(label, f) {
    run_test(label, (helpers) => {
        pm_conversations.clear_for_testing();
        recent_senders.clear_for_testing();
        peer_data.clear_for_testing();
        people.clear_recipient_counts_for_testing();
        helpers.override(current_user, "is_admin", false);
        helpers.override(realm, "realm_is_zephyr_mirror_realm", false);

        f(helpers);
    });
}

test("sort_streams", ({override}) => {
    let test_streams = [
        {
            stream_id: 101,
            name: "Dev",
            pin_to_top: false,
            stream_weekly_traffic: 0,
            subscribed: true,
            is_muted: false,
            is_recently_active: true,
        },
        {
            stream_id: 102,
            name: "Docs",
            pin_to_top: false,
            stream_weekly_traffic: 100,
            subscribed: true,
            is_muted: false,
            is_recently_active: true,
        },
        {
            stream_id: 103,
            name: "Derp",
            pin_to_top: false,
            stream_weekly_traffic: 0,
            subscribed: true,
            is_muted: true,
            is_recently_active: true,
        },
        {
            stream_id: 104,
            name: "Denmark",
            pin_to_top: true,
            stream_weekly_traffic: 100,
            subscribed: true,
            is_muted: false,
            is_recently_active: true,
        },
        {
            stream_id: 105,
            name: "dead",
            pin_to_top: false,
            stream_weekly_traffic: 0,
            subscribed: true,
            is_muted: false,
            is_recently_active: false,
        },
        {
            stream_id: 106,
            name: "dead (almost)",
            pin_to_top: false,
            stream_weekly_traffic: 2,
            subscribed: true,
            is_muted: false,
            is_recently_active: true,
        },
    ];

    override(
        user_settings,
        "demote_inactive_streams",
        settings_config.demote_inactive_streams_values.always.code,
    );

    stream_list_sort.set_filter_out_inactives();
    compose_state.set_selected_recipient_id(dev_sub.stream_id);

    test_streams = th.sort_streams(test_streams, "d");
    assert.deepEqual(test_streams[0].name, "Dev"); // Stream being composed to
    assert.deepEqual(test_streams[1].name, "Denmark"); // Pinned stream
    assert.deepEqual(test_streams[2].name, "Docs"); // Active stream
    assert.deepEqual(test_streams[3].name, "dead (almost)"); // Relatively inactive stream
    assert.deepEqual(test_streams[4].name, "dead"); // Completely inactive stream
    assert.deepEqual(test_streams[5].name, "Derp"); // Muted stream last

    // Sort streams by name
    test_streams = th.sort_streams_by_name(test_streams, "d");
    assert.deepEqual(test_streams[0].name, "dead");
    assert.deepEqual(test_streams[1].name, "dead (almost)");
    assert.deepEqual(test_streams[2].name, "Denmark");
    assert.deepEqual(test_streams[3].name, "Derp");
    assert.deepEqual(test_streams[4].name, "Dev");
    assert.deepEqual(test_streams[5].name, "Docs");

    compose_state.set_selected_recipient_id(linux_sub.stream_id);

    // Test sort streams with description
    test_streams = [
        {
            stream_id: 201,
            name: "Dev",
            description: "development help",
            subscribed: true,
            is_recently_active: true,
        },
        {
            stream_id: 202,
            name: "Docs",
            description: "writing docs",
            subscribed: true,
            is_recently_active: true,
        },
        {
            stream_id: 203,
            name: "Derp",
            description: "derping around",
            subscribed: true,
            is_recently_active: true,
        },
        {
            stream_id: 204,
            name: "Denmark",
            description: "visiting Denmark",
            subscribed: true,
            is_recently_active: true,
        },
        {
            stream_id: 205,
            name: "dead",
            description: "dead stream",
            subscribed: true,
            is_recently_active: false,
        },
    ];

    test_streams = th.sort_streams(test_streams, "wr");
    assert.deepEqual(test_streams[0].name, "Docs"); // Description match
    assert.deepEqual(test_streams[1].name, "Denmark"); // Popular stream
    assert.deepEqual(test_streams[2].name, "Derp"); // Less subscribers
    assert.deepEqual(test_streams[3].name, "Dev"); // Alphabetically last
    assert.deepEqual(test_streams[4].name, "dead"); // Inactive streams last

    // Test sort both subscribed and unsubscribed streams.
    test_streams = [
        {
            stream_id: 301,
            name: "Dev",
            description: "Some devs",
            subscribed: true,
        },
        {
            stream_id: 302,
            name: "East",
            description: "Developing east",
            subscribed: true,
        },
        {
            stream_id: 303,
            name: "New",
            description: "No match",
            subscribed: true,
        },
        {
            stream_id: 304,
            name: "Derp",
            description: "Always derping",
            subscribed: false,
        },
        {
            stream_id: 305,
            name: "Ether",
            description: "Destroying ether",
            subscribed: false,
        },
        {
            stream_id: 306,
            name: "Mew",
            description: "Cat mews",
            subscribed: false,
        },
    ];

    test_streams = th.sort_streams(test_streams, "d");
    assert.deepEqual(test_streams[0].name, "Dev"); // Subscribed and stream name starts with query
    assert.deepEqual(test_streams[1].name, "Derp"); // Unsubscribed and stream name starts with query
    assert.deepEqual(test_streams[2].name, "East"); // Subscribed and description starts with query
    assert.deepEqual(test_streams[3].name, "Ether"); // Unsubscribed and description starts with query
    assert.deepEqual(test_streams[4].name, "New"); // Subscribed and no match
    assert.deepEqual(test_streams[5].name, "Mew"); // Unsubscribed and no match
});

function language_items(languages) {
    return languages.map((language) => ({
        language,
        type: "syntax",
    }));
}

test("sort_languages", ({override, override_rewire}) => {
    override(realm, "realm_default_code_block_language", "dart");
    const default_language = realm.realm_default_code_block_language;

    override_rewire(pygments_data, "langs", {
        python: {priority: 26},
        javascript: {priority: 27},
        php: {priority: 16},
        pascal: {priority: 15},
        perl: {priority: 3},
        css: {priority: 21},
        spoiler: {priority: 29},
        text: {priority: 31},
        quote: {priority: 30},
        math: {priority: 28},
    });

    let test_langs = language_items(["pascal", "perl", "php", "python", "spoiler", "javascript"]);
    test_langs = th.sort_languages(test_langs, "p");

    // Sort languages by matching first letter, and then by popularity
    assert.deepEqual(
        test_langs,
        language_items(["python", "php", "pascal", "perl", "spoiler", "javascript"]),
    );

    // Test if popularity between two languages are the same
    pygments_data.langs.php = {priority: 26};
    test_langs = language_items(["pascal", "perl", "php", "python", "spoiler", "javascript"]);
    test_langs = th.sort_languages(test_langs, "p");

    assert.deepEqual(
        test_langs,
        language_items(["php", "python", "pascal", "perl", "spoiler", "javascript"]),
    );

    test_langs = language_items([
        default_language,
        "text",
        "quote",
        "math",
        "python",
        "javascript",
    ]);
    const test_langs_for_default = th.sort_languages(test_langs, "d");

    assert.deepEqual(
        test_langs_for_default,
        language_items([default_language, "text", "quote", "math", "javascript", "python"]),
    );

    test_langs = th.sort_languages(test_langs, "t");

    assert.deepEqual(
        test_langs,
        language_items(["text", "quote", "math", "javascript", "python", default_language]),
    );
});

test("sort_languages on actual data", () => {
    // Some final tests on the actual pygments data to check ordering.
    //
    // We may eventually want to use human-readable names like
    // "JavaScript" with several machine-readable aliases for what the
    // user typed, which might help provide a better user experience.
    let test_langs = language_items(["j", "java", "javascript", "js"]);

    // Sort according to priority only.
    test_langs = th.sort_languages(test_langs, "jav");
    assert.deepEqual(test_langs, language_items(["javascript", "java", "j"]));

    // Push exact matches to top, regardless of priority
    test_langs = th.sort_languages(test_langs, "java");
    assert.deepEqual(test_langs, language_items(["java", "javascript", "j"]));
    test_langs = th.sort_languages(test_langs, "j");
    assert.deepEqual(test_langs, language_items(["j", "javascript", "java"]));

    // (Only one alias should be shown per language
    // (e.g. searching for "js" shouldn't show "javascript")
    test_langs = language_items(["js", "javascript", "java"]);
    test_langs = th.sort_languages(test_langs, "js");
    assert.deepEqual(test_langs, language_items(["js", "java"]));
});

test("sort_user_groups", () => {
    const test_user_groups = [
        {
            id: 1,
            name: "Developers",
            description: "Group of developers",
        },
        {
            id: 2,
            name: "Designers",
            description: "Group of designers",
        },
        {
            id: 3,
            name: "DevOps",
            description: "Group of DevOps engineers",
        },
        {
            id: 4,
            name: "Docs",
            description: "Group of documentation writers",
        },
        {
            id: 5,
            name: "Devs",
            description: "Another group of developers",
        },
    ];

    // Test sorting by user group name
    let sorted_user_groups = th.sort_user_groups(test_user_groups, "De");

    // Assert that the groups are sorted correctly by name
    assert.deepEqual(sorted_user_groups[0].name, "Designers"); // Exact match with query
    assert.deepEqual(sorted_user_groups[1].name, "Developers");
    assert.deepEqual(sorted_user_groups[2].name, "DevOps");
    assert.deepEqual(sorted_user_groups[3].name, "Devs");
    assert.deepEqual(sorted_user_groups[4].name, "Docs");

    // Test sorting with a different query
    sorted_user_groups = th.sort_user_groups(test_user_groups, "Do");

    assert.deepEqual(sorted_user_groups[0].name, "Docs"); // Exact match with query
    assert.deepEqual(sorted_user_groups[1].name, "Designers");
    assert.deepEqual(sorted_user_groups[2].name, "Developers");
    assert.deepEqual(sorted_user_groups[3].name, "DevOps");
    assert.deepEqual(sorted_user_groups[4].name, "Devs");
});

function get_typeahead_result(query, current_stream_id, current_topic) {
    const users = people.get_realm_users().map((user) => ({type: "user", user}));
    const result = th.sort_recipients({
        users,
        query,
        current_stream_id,
        current_topic,
    });
    return result.map((person) => person.user.email);
}

test("sort_recipients", () => {
    // Typeahead for recipientbox [query, "", undefined]
    assert.deepEqual(get_typeahead_result("b", ""), [
        "b_user_1@zulip.net",
        "b_user_2@zulip.net",
        "b_user_3@zulip.net",
        "b_bot@example.com",
        "a_bot@zulip.com",
        "a_user@zulip.org",
        "zman@test.net",
    ]);

    // Test match by email (To get coverage for ok_users and ok_bots)
    assert.deepEqual(get_typeahead_result("b_user_1@zulip.net", ""), [
        "b_user_1@zulip.net",
        "a_user@zulip.org",
        "b_user_2@zulip.net",
        "b_user_3@zulip.net",
        "zman@test.net",
        "a_bot@zulip.com",
        "b_bot@example.com",
    ]);

    // Typeahead for direct message [query, "", ""]
    assert.deepEqual(get_typeahead_result("a", "", ""), [
        "a_user@zulip.org",
        "a_bot@zulip.com",
        "b_user_1@zulip.net",
        "b_user_2@zulip.net",
        "b_user_3@zulip.net",
        "zman@test.net",
        "b_bot@example.com",
    ]);

    const subscriber_email_1 = "b_user_2@zulip.net";
    const subscriber_email_2 = "b_user_3@zulip.net";
    const subscriber_email_3 = "b_bot@example.com";
    peer_data.add_subscriber(1, people.get_user_id(subscriber_email_1));
    peer_data.add_subscriber(1, people.get_user_id(subscriber_email_2));
    peer_data.add_subscriber(1, people.get_user_id(subscriber_email_3));

    // For splitting based on whether a direct message was sent
    pm_conversations.set_partner(5);
    pm_conversations.set_partner(6);
    pm_conversations.set_partner(2);
    pm_conversations.set_partner(7);

    // For splitting based on recency
    recent_senders.process_stream_message({
        sender_id: 7,
        stream_id: 1,
        topic: "Dev topic",
        id: (next_id += 1),
    });
    recent_senders.process_stream_message({
        sender_id: 5,
        stream_id: 1,
        topic: "Dev topic",
        id: (next_id += 1),
    });
    recent_senders.process_stream_message({
        sender_id: 6,
        stream_id: 1,
        topic: "Dev topic",
        id: (next_id += 1),
    });

    // Typeahead for stream message [query, stream-id, topic-name]
    assert.deepEqual(get_typeahead_result("b", dev_sub.stream_id, "Dev topic"), [
        subscriber_email_2,
        subscriber_email_1,
        "b_user_1@zulip.net",
        subscriber_email_3,
        "a_bot@zulip.com",
        "zman@test.net",
        "a_user@zulip.org",
    ]);

    recent_senders.process_stream_message({
        sender_id: 5,
        stream_id: 2,
        topic: "Linux topic",
        id: (next_id += 1),
    });
    recent_senders.process_stream_message({
        sender_id: 7,
        stream_id: 2,
        topic: "Linux topic",
        id: (next_id += 1),
    });

    // No match
    assert.deepEqual(get_typeahead_result("h", linux_sub.stream_id, "Linux topic"), [
        "zman@test.net",
        "b_user_3@zulip.net",
        "a_user@zulip.org",
        "b_user_1@zulip.net",
        "b_user_2@zulip.net",
        "b_bot@example.com",
        "a_bot@zulip.com",
    ]);
});

test("sort_recipients all mention", () => {
    compose_state.set_message_type("stream");
    const all_obj = ct.broadcast_mentions()[0];
    assert.equal(all_obj.email, "all");
    assert.equal(all_obj.idx, 0);

    // Test person email is "all" or "everyone"
    const user_and_mention_items = [
        ...matches.map((user) => user_item(user)),
        broadcast_item(all_obj),
    ];
    const results = th.sort_recipients({
        users: user_and_mention_items,
        query: "a",
        current_stream_id: linux_sub.stream_id,
        current_topic: "Linux topic",
    });

    assertSameEmails(results, [
        broadcast_item(all_obj),
        a_user_item,
        a_bot_item,
        b_user_1_item,
        b_user_2_item,
        b_user_3_item,
        zman_item,
        b_bot_item,
    ]);
});

test("sort_recipients pm counts", () => {
    // Test sort_recipients with pm counts
    people.set_recipient_count_for_testing(a_bot.user_id, 50);
    people.set_recipient_count_for_testing(a_user.user_id, 2);
    people.set_recipient_count_for_testing(b_user_1.user_id, 32);
    people.set_recipient_count_for_testing(b_user_2.user_id, 42);
    people.set_recipient_count_for_testing(b_user_3.user_id, 0);
    people.set_recipient_count_for_testing(b_bot.user_id, 1);

    assert.deepEqual(get_typeahead_result("b"), [
        "b_user_2@zulip.net",
        "b_user_1@zulip.net",
        "b_user_3@zulip.net",
        "b_bot@example.com",
        "a_bot@zulip.com",
        "a_user@zulip.org",
        "zman@test.net",
    ]);

    // Now prioritize stream membership over pm counts.
    peer_data.add_subscriber(linux_sub.stream_id, b_user_3.user_id);

    assert.deepEqual(get_typeahead_result("b", linux_sub.stream_id, "Linux topic"), [
        "b_user_3@zulip.net",
        "b_user_2@zulip.net",
        "b_user_1@zulip.net",
        "b_bot@example.com",
        "a_bot@zulip.com",
        "a_user@zulip.org",
        "zman@test.net",
    ]);

    /* istanbul ignore next */
    function compare() {
        throw new Error("We do not expect to need a tiebreaker here.");
    }

    // get some line coverage
    assert.equal(
        th.compare_people_for_relevance(b_user_1_item, b_user_3_item, compare, linux_sub.stream_id),
        1,
    );
    assert.equal(
        th.compare_people_for_relevance(b_user_3_item, b_user_1_item, compare, linux_sub.stream_id),
        -1,
    );
});

test("sort_recipients dup bots", () => {
    const dup_objects = [...matches, a_bot];
    const user_items = dup_objects.map((user) => user_item(user));
    const recipients = th.sort_recipients({
        users: user_items,
        query: "b",
        current_stream_id: undefined,
        current_topic: "",
    });
    const recipients_email = recipients.map((person) => person.user.email);
    const expected = [
        "b_user_1@zulip.net",
        "b_user_2@zulip.net",
        "b_user_3@zulip.net",
        "b_bot@example.com",
        "a_bot@zulip.com",
        "a_bot@zulip.com",
        "a_user@zulip.org",
        "zman@test.net",
    ];
    assert.deepEqual(recipients_email, expected);
});

test("sort_recipients dup alls", () => {
    compose_state.set_message_type("stream");
    const all_obj_item = broadcast_item(ct.broadcast_mentions()[0]);

    // full_name starts with same character but emails are 'all'
    const user_and_mention_items = [all_obj_item, a_user_item, all_obj_item];
    const recipients = th.sort_recipients({
        users: user_and_mention_items,
        query: "a",
        current_stream_id: linux_sub.stream_id,
        current_topic: "Linux topic",
    });

    const expected = [all_obj_item, a_user_item];
    assertSameEmails(recipients, expected);
});

test("sort_recipients dup alls direct message", () => {
    compose_state.set_message_type("private");
    const all_obj_item = broadcast_item(ct.broadcast_mentions()[0]);

    // full_name starts with same character but emails are 'all'
    const user_and_mention_items = [all_obj_item, a_user_item, all_obj_item];
    const recipients = th.sort_recipients({
        users: user_and_mention_items,
        query: "a",
    });

    const expected = [a_user_item, all_obj_item];
    assertSameEmails(recipients, expected);
});

test("sort_recipients subscribers", () => {
    // b_user_2 is a subscriber and b_user_1 is not.
    peer_data.add_subscriber(dev_sub.stream_id, b_user_2.user_id);
    const user_items = [b_user_2_item, b_user_1_item];
    const recipients = th.sort_recipients({
        users: user_items,
        query: "b",
        current_stream_id: dev_sub.stream_id,
        current_topic: "Dev topic",
    });
    const recipients_email = recipients.map((person) => person.user.email);
    const expected = ["b_user_2@zulip.net", "b_user_1@zulip.net"];
    assert.deepEqual(recipients_email, expected);
});

test("sort_recipients recent senders", () => {
    // b_user_2 is the only recent sender, b_user_3 is the only pm partner
    // and all are subscribed to the stream Linux.
    peer_data.add_subscriber(linux_sub.stream_id, b_user_1.user_id);
    peer_data.add_subscriber(linux_sub.stream_id, b_user_2.user_id);
    peer_data.add_subscriber(linux_sub.stream_id, b_user_3.user_id);
    recent_senders.process_stream_message({
        sender_id: b_user_2.user_id,
        stream_id: linux_sub.stream_id,
        topic: "Linux topic",
        id: (next_id += 1),
    });
    pm_conversations.set_partner(b_user_3.user_id);
    const user_items = [b_user_1_item, b_user_2_item, b_user_3_item];
    const recipients = th.sort_recipients({
        users: user_items,
        query: "b",
        current_stream_id: linux_sub.stream_id,
        current_topic: "Linux topic",
    });
    const recipients_email = recipients.map((person) => person.user.email);
    // Prefer recent sender over pm partner
    const expected = ["b_user_2@zulip.net", "b_user_3@zulip.net", "b_user_1@zulip.net"];
    assert.deepEqual(recipients_email, expected);
});

test("sort_recipients pm partners", () => {
    // b_user_3 is a pm partner and b_user_2 is not and
    // both are not subscribed to the stream Linux.
    pm_conversations.set_partner(b_user_3.user_id);
    const user_items = [b_user_3_item, b_user_2_item];
    const recipients = th.sort_recipients({
        users: user_items,
        query: "b",
        current_stream_id: linux_sub.stream_id,
        current_topic: "Linux topic",
    });
    const recipients_email = recipients.map((person) => person.user.email);
    const expected = ["b_user_3@zulip.net", "b_user_2@zulip.net"];
    assert.deepEqual(recipients_email, expected);
});

test("sort broadcast mentions for stream message type", () => {
    // test the normal case, which is that the
    // broadcast mentions are already sorted (we
    // actually had a bug where the sort would
    // randomly rearrange them)
    compose_state.set_message_type("stream");
    const mentions = ct.broadcast_mentions().reverse();
    const broadcast_items = mentions.map((broadcast) => broadcast_item(broadcast));
    const results = th.sort_people_for_relevance(broadcast_items, "", "");

    assert.deepEqual(
        results.map((r) => r.user.email),
        ["all", "everyone", "stream", "channel", "topic"],
    );

    // Reverse the list to test actual sorting
    // and ensure test coverage for the defensive
    // code.  Also, add in some people users.
    const user_or_mention_items = [
        zman_item,
        ...ct
            .broadcast_mentions()
            .map((broadcast) => broadcast_item(broadcast))
            .reverse(),
        a_user_item,
    ];
    const results2 = th.sort_people_for_relevance(user_or_mention_items, "", "");

    assert.deepEqual(
        results2.map((r) => r.user.email),
        ["all", "everyone", "stream", "channel", "topic", a_user.email, zman.email],
    );
});

test("sort broadcast mentions for direct message type", () => {
    compose_state.set_message_type("private");
    const mentions = ct.broadcast_mentions().reverse();
    const broadcast_items = mentions.map((broadcast) => broadcast_item(broadcast));
    const results = th.sort_people_for_relevance(broadcast_items, "", "");

    assert.deepEqual(
        results.map((r) => r.user.email),
        ["all", "everyone"],
    );

    const user_or_mention_items = [
        zman_item,
        ...ct
            .broadcast_mentions()
            .map((broadcast) => broadcast_item(broadcast))
            .reverse(),
        a_user_item,
    ];
    const results2 = th.sort_people_for_relevance(user_or_mention_items, "", "");

    assert.deepEqual(
        results2.map((r) => r.user.email),
        [a_user.email, zman.email, "all", "everyone"],
    );
});

test("test compare directly for stream message type", () => {
    // This is important for ensuring test coverage.
    // We don't technically need it now, but our test
    // coverage is subject to the whims of how JS sorts.
    compose_state.set_message_type("stream");
    const all_obj = ct.broadcast_mentions()[0];
    const all_obj_item = broadcast_item(all_obj);

    assert.equal(th.compare_people_for_relevance(all_obj_item, all_obj_item), 0);
    assert.equal(th.compare_people_for_relevance(all_obj_item, zman_item), -1);
    assert.equal(th.compare_people_for_relevance(zman_item, all_obj_item), 1);
});

test("test compare directly for direct message", () => {
    compose_state.set_message_type("private");
    const all_obj = ct.broadcast_mentions()[0];
    const all_obj_item = broadcast_item(all_obj);

    assert.equal(th.compare_people_for_relevance(all_obj_item, all_obj_item), 0);
    assert.equal(th.compare_people_for_relevance(all_obj_item, zman_item), 1);
    assert.equal(th.compare_people_for_relevance(zman_item, all_obj_item), -1);
});

test("render_person when emails hidden", ({mock_template, override}) => {
    // Test render_person with regular person, under hidden email visibility case
    override(realm, "custom_profile_field_types", {
        PRONOUNS: {id: 8, name: "Pronouns"},
    });
    let rendered = false;
    mock_template("typeahead_list_item.hbs", false, (args) => {
        assert.equal(args.primary, b_user_1.full_name);
        assert.equal(args.secondary, undefined);
        rendered = true;
        return "typeahead-item-stub";
    });
    assert.equal(th.render_person(b_user_1_item), "typeahead-item-stub");
    assert.ok(rendered);
});

test("render_person", ({mock_template, override}) => {
    // Test render_person with regular person
    a_user.delivery_email = "a_user_delivery@zulip.org";
    override(realm, "custom_profile_field_types", {
        PRONOUNS: {id: 8, name: "Pronouns"},
    });
    let rendered = false;
    mock_template("typeahead_list_item.hbs", false, (args) => {
        assert.equal(args.primary, a_user.full_name);
        assert.equal(args.secondary, a_user.delivery_email);
        rendered = true;
        return "typeahead-item-stub";
    });
    assert.equal(th.render_person(a_user_item), "typeahead-item-stub");
    assert.ok(rendered);
});

test("render_person special_item_text", ({mock_template}) => {
    let rendered = false;

    // Test render_person with special_item_text person
    const special_person = {
        email: "special@example.com",
        full_name: "Special person",
        is_admin: false,
        is_bot: false,
        user_id: 7,
        special_item_text: "special_text",
    };

    rendered = false;
    mock_template("typeahead_list_item.hbs", false, (args) => {
        assert.equal(args.primary, special_person.special_item_text);
        rendered = true;
        return "typeahead-item-stub";
    });
    assert.equal(th.render_person(broadcast_item(special_person)), "typeahead-item-stub");
    assert.ok(rendered);
});

test("render_stream", ({mock_template}) => {
    // Test render_stream with short description
    let rendered = false;
    const stream = {
        description: "This is the description of the test stream.",
        rendered_description: "This is the description of the test stream.",
        stream_id: 42,
        name: "test stream",
    };

    mock_template("typeahead_list_item.hbs", false, (args) => {
        assert.equal(args.stream, stream);
        assert.equal(args.secondary_html, stream.rendered_description);
        rendered = true;
        return "typeahead-item-stub";
    });
    assert.equal(th.render_stream(stream), "typeahead-item-stub");
    assert.ok(rendered);
});

test("render_stream_topic", ({mock_template}) => {
    let rendered = false;
    const streamData = {
        invite_only: true,
        is_web_public: false,
        color: "blue",
        name: "Design",
        description: "Design related discussions.",
        rendered_description: "",
        subscribed: true,
    };

    const topic_object = {
        topic: "Test topic title",
        stream_data: {
            invite_only: true,
            is_web_public: false,
            color: "blue",
            name: "Design",
            description: "Design related discussions.",
            rendered_description: "",
            subscribed: true,
        },
        type: "topic_list",
        is_stream_only: false,
    };

    mock_template("typeahead_list_item.hbs", false, (args) => {
        assert.equal(args.topic, "Test topic title");
        assert.equal(args.type, "topic_list");
        assert.equal(args.is_stream_only, false);
        assert.equal(args.is_stream_topic, true);
        assert.deepEqual(args.stream_data, streamData);
        rendered = true;
        return "typeahead-item-stub";
    });
    assert.equal(th.render_stream_topic(topic_object), "typeahead-item-stub");
    assert.ok(rendered);
});

test("render_emoji", ({mock_template}) => {
    // Test render_emoji with normal emoji.
    let expected_template_data = {
        primary: "thumbs up",
        emoji_code: "1f44d",
        is_emoji: true,
        has_image: false,
        has_pronouns: false,
        has_secondary: false,
        has_secondary_html: false,
        has_status: false,
    };
    let rendered = false;
    let test_emoji = {
        emoji_name: "thumbs_up",
        emoji_code: "1f44d",
    };
    emoji.active_realm_emojis.clear();
    emoji.active_realm_emojis.set("realm_emoji", "TBD");

    mock_template("typeahead_list_item.hbs", false, (args) => {
        assert.deepEqual(args, expected_template_data);
        rendered = true;
        return "typeahead-item-stub";
    });
    assert.equal(th.render_emoji(test_emoji), "typeahead-item-stub");
    assert.ok(rendered);

    // Test render_emoji with normal emoji.
    rendered = false;
    expected_template_data = {
        primary: "realm emoji",
        img_src: "TBD",
        is_emoji: true,
        has_image: true,
        has_pronouns: false,
        has_secondary: false,
        has_secondary_html: false,
        has_status: false,
    };
    test_emoji = {
        emoji_name: "realm_emoji",
        emoji_url: "TBD",
    };

    assert.equal(th.render_emoji(test_emoji), "typeahead-item-stub");
    assert.ok(rendered);
});

test("sort_slash_commands", () => {
    const slash_commands = [
        {name: "my"},
        {name: "poll"},
        {name: "me"},
        {name: "mine"},
        {name: "test"},
        {name: "ping"},
    ];
    assert.deepEqual(th.sort_slash_commands(slash_commands, "m"), [
        {name: "me"},
        {name: "mine"},
        {name: "my"},
        {name: "ping"},
        {name: "poll"},
        {name: "test"},
    ]);
});

test("compare_language", () => {
    assert.ok(th.compare_language("javascript", "haskell") < 0);
    assert.ok(th.compare_language("haskell", "javascript") > 0);

    // "abap" and "amdgpu" both have priority = 0 at this time, so there is a tie.
    // Alphabetical order should be used to break that tie.
    assert.equal(th.compare_language("abap", "amdgpu"), util.strcmp("abap", "amdgpu"));

    // Test with languages that aren't in the generated pygments data.
    assert.equal(pygments_data.langs.custom_a, undefined);
    assert.equal(pygments_data.langs.custom_b, undefined);
    // Since custom_a has no popularity score, it gets sorted behind python.
    assert.equal(th.compare_language("custom_a", "python"), 1);
    assert.equal(th.compare_language("python", "custom_a"), -1);
    // Whenever there is a tie, even in the case neither have a popularity
    // score, then alphabetical order is used to break the tie.
    assert.equal(th.compare_language("custom_a", "custom_b"), util.strcmp("custom_a", "custom_b"));
});

// TODO: This is incomplete for testing this function, and
// should be filled out more. This case was added for codecov.
test("compare_by_pms", () => {
    assert.equal(th.compare_by_pms(a_user, a_user), 0);
});

test("sort_group_setting_options", ({override_rewire}) => {
    function get_group_setting_typeahead_result(query, target_group) {
        const users = people.get_realm_active_human_users().map((user) => ({type: "user", user}));
        const groups = user_groups.get_all_realm_user_groups().map((group) => ({
            type: "user_group",
            ...group,
        }));
        const result = th.sort_group_setting_options({
            users,
            query,
            groups,
            target_group,
        });
        return result.map((item) => {
            if (item.type === "user") {
                return item.user.full_name;
            }

            return item.name;
        });
    }

    assert.deepEqual(get_group_setting_typeahead_result("Bo", second_bob_group), [
        bob_system_group.name,
        bob_group.name,
        second_bob_group.name,
        b_user_2.full_name,
        b_user_1.full_name,
        b_user_3.full_name,
        everyone_group.name,
        members_group.name,
        admins_group.name,
        a_user.full_name,
        zman.full_name,
    ]);

    assert.deepEqual(get_group_setting_typeahead_result("bo", second_bob_group), [
        bob_system_group.name,
        bob_group.name,
        second_bob_group.name,
        b_user_2.full_name,
        b_user_1.full_name,
        b_user_3.full_name,
        everyone_group.name,
        members_group.name,
        admins_group.name,
        a_user.full_name,
        zman.full_name,
    ]);

    assert.deepEqual(get_group_setting_typeahead_result("Z", second_bob_group), [
        zman.full_name,
        admins_group.name,
        a_user.full_name,
        bob_system_group.name,
        everyone_group.name,
        members_group.name,
        bob_group.name,
        second_bob_group.name,
        b_user_2.full_name,
        b_user_1.full_name,
        b_user_3.full_name,
    ]);

    assert.deepEqual(get_group_setting_typeahead_result("me", second_bob_group), [
        members_group.name,
        bob_system_group.name,
        everyone_group.name,
        admins_group.name,
        bob_group.name,
        second_bob_group.name,
        b_user_2.full_name,
        a_user.full_name,
        b_user_1.full_name,
        b_user_3.full_name,
        zman.full_name,
    ]);

    assert.deepEqual(get_group_setting_typeahead_result("ever", second_bob_group), [
        everyone_group.name,
        members_group.name,
        bob_system_group.name,
        admins_group.name,
        bob_group.name,
        second_bob_group.name,
        b_user_2.full_name,
        a_user.full_name,
        b_user_1.full_name,
        b_user_3.full_name,
        zman.full_name,
    ]);

    assert.deepEqual(get_group_setting_typeahead_result("translated: members", second_bob_group), [
        members_group.name,
        bob_system_group.name,
        everyone_group.name,
        admins_group.name,
        bob_group.name,
        second_bob_group.name,
        b_user_2.full_name,
        a_user.full_name,
        b_user_1.full_name,
        b_user_3.full_name,
        zman.full_name,
    ]);

    override_rewire(bootstrap_typeahead, "MAX_ITEMS", 6);
    assert.deepEqual(get_group_setting_typeahead_result("Bo", second_bob_group), [
        bob_system_group.name,
        bob_group.name,
        second_bob_group.name,
        b_user_2.full_name,
        b_user_1.full_name,
        b_user_3.full_name,
    ]);
});

test("compare_group_setting_options", () => {
    // User group has higher priority than user.
    assert.equal(th.compare_group_setting_options(a_user_item, bob_group_item, bob_group), 1);
    assert.equal(th.compare_group_setting_options(bob_group_item, a_user_item, bob_group), -1);

    // System user group has higher priority than other user groups.
    assert.equal(
        th.compare_group_setting_options(bob_group_item, bob_system_group_item, bob_group),
        1,
    );
    assert.equal(
        th.compare_group_setting_options(bob_system_group_item, bob_group_item, bob_group),
        -1,
    );
    assert.equal(
        th.compare_group_setting_options(admins_group_item, bob_system_group_item, bob_group),
        1,
    );

    // In case both groups are not system groups, alphabetical order is used to decide priority.
    assert.equal(th.compare_group_setting_options(bob_group_item, admins_group_item, bob_group), 1);
    assert.equal(
        th.compare_group_setting_options(admins_group_item, bob_group_item, bob_group),
        -1,
    );

    // A user who is a member of the group being changed has higher priority.
    // If both the users are not members of the group being changed, alphabetical order
    // is used to decide priority.
    assert.equal(th.compare_group_setting_options(b_user_1_item, b_user_2_item, bob_group), -1);
    assert.equal(
        th.compare_group_setting_options(b_user_1_item, b_user_2_item, second_bob_group),
        1,
    );

    // Get coverage for case where two users have same names. Original order is preserved
    // in such cases.
    assert.equal(th.compare_group_setting_options(b_user_1_item, b_user_1_item, bob_group), 0);
});

test("sort_stream_or_group_members_options", ({override_rewire}) => {
    function get_stream_or_group_members_typeahead_result(query) {
        const users = people.get_realm_active_human_users().map((user) => ({type: "user", user}));
        const groups = user_groups.get_all_realm_user_groups().map((group) => ({
            type: "user_group",
            ...group,
        }));
        const result = th.sort_stream_or_group_members_options({
            users,
            query,
            groups,
            for_stream_subscribers: true,
        });
        return result.map((item) => {
            if (item.type === "user") {
                return item.user.full_name;
            }

            return item.name;
        });
    }

    assert.deepEqual(get_stream_or_group_members_typeahead_result("Bo"), [
        bob_group.name,
        second_bob_group.name,
        b_user_1.full_name,
        b_user_2.full_name,
        b_user_3.full_name,
        bob_system_group.name,
        members_group.name,
        admins_group.name,
        a_user.full_name,
        zman.full_name,
        everyone_group.name,
    ]);

    assert.deepEqual(get_stream_or_group_members_typeahead_result("bo"), [
        bob_group.name,
        second_bob_group.name,
        b_user_1.full_name,
        b_user_2.full_name,
        b_user_3.full_name,
        bob_system_group.name,
        members_group.name,
        admins_group.name,
        a_user.full_name,
        zman.full_name,
        everyone_group.name,
    ]);

    assert.deepEqual(get_stream_or_group_members_typeahead_result("Z"), [
        zman.full_name,
        admins_group.name,
        a_user.full_name,
        members_group.name,
        bob_group.name,
        second_bob_group.name,
        b_user_1.full_name,
        b_user_2.full_name,
        b_user_3.full_name,
        bob_system_group.name,
        everyone_group.name,
    ]);

    assert.deepEqual(get_stream_or_group_members_typeahead_result("me"), [
        members_group.name,
        admins_group.name,
        bob_group.name,
        second_bob_group.name,
        a_user.full_name,
        b_user_1.full_name,
        b_user_2.full_name,
        b_user_3.full_name,
        zman.full_name,
        bob_system_group.name,
        everyone_group.name,
    ]);

    assert.deepEqual(get_stream_or_group_members_typeahead_result("ever"), [
        members_group.name,
        everyone_group.name,
        admins_group.name,
        bob_group.name,
        second_bob_group.name,
        a_user.full_name,
        b_user_1.full_name,
        b_user_2.full_name,
        b_user_3.full_name,
        zman.full_name,
        bob_system_group.name,
    ]);

    assert.deepEqual(get_stream_or_group_members_typeahead_result("translated: members"), [
        members_group.name,
        admins_group.name,
        bob_group.name,
        second_bob_group.name,
        a_user.full_name,
        b_user_1.full_name,
        b_user_2.full_name,
        b_user_3.full_name,
        zman.full_name,
        bob_system_group.name,
        everyone_group.name,
    ]);

    override_rewire(bootstrap_typeahead, "MAX_ITEMS", 6);
    assert.deepEqual(get_stream_or_group_members_typeahead_result("Bo"), [
        bob_group.name,
        second_bob_group.name,
        b_user_1.full_name,
        b_user_2.full_name,
        b_user_3.full_name,
        bob_system_group.name,
    ]);
});

test("compare_stream_or_group_members_options", () => {
    // Non system user group has higher priority than user for both streams and groups UI.
    assert.equal(
        th.compare_stream_or_group_members_options(a_user_item, bob_group_item, undefined, true),
        1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(a_user_item, bob_group_item, undefined, false),
        1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(bob_group_item, a_user_item, undefined, true),
        -1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(bob_group_item, a_user_item, undefined, false),
        -1,
    );
    // User has higher priority than non `role:members` system user group for streams UI.
    assert.equal(
        th.compare_stream_or_group_members_options(
            a_user_item,
            bob_system_group_item,
            undefined,
            true,
        ),
        -1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            bob_system_group_item,
            a_user_item,
            undefined,
            true,
        ),
        1,
    );
    // System user group has lower priority than other user groups for both streams and groups UI.
    assert.equal(
        th.compare_stream_or_group_members_options(
            bob_group_item,
            bob_system_group_item,
            undefined,
            true,
        ),
        -1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            bob_group_item,
            bob_system_group_item,
            undefined,
            false,
        ),
        -1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            bob_system_group_item,
            bob_group_item,
            undefined,
            true,
        ),
        1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            bob_system_group_item,
            bob_group_item,
            undefined,
            false,
        ),
        1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            admins_group_item,
            bob_system_group_item,
            undefined,
            true,
        ),
        -1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            admins_group_item,
            bob_system_group_item,
            undefined,
            false,
        ),
        -1,
    );

    // Members group always takes priority against any other group for stream subscribers UI.
    assert.equal(
        th.compare_stream_or_group_members_options(
            bob_group_item,
            members_group_item,
            undefined,
            true,
        ),
        1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            members_group_item,
            bob_group_item,
            undefined,
            true,
        ),
        -1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            admins_group_item,
            members_group_item,
            undefined,
            true,
        ),
        1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            members_group_item,
            admins_group_item,
            undefined,
            true,
        ),
        -1,
    );
    // For group members UI, members group does not take priority.
    assert.equal(
        th.compare_stream_or_group_members_options(
            bob_group_item,
            members_group_item,
            undefined,
            false,
        ),
        -1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            members_group_item,
            bob_group_item,
            undefined,
            false,
        ),
        1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            admins_group_item,
            members_group_item,
            undefined,
            false,
        ),
        -1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            members_group_item,
            admins_group_item,
            undefined,
            false,
        ),
        1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            a_user_item,
            members_group_item,
            undefined,
            false,
        ),
        -1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            members_group_item,
            a_user_item,
            undefined,
            false,
        ),
        1,
    );

    // In case both groups are not system groups, alphabetical order is used to decide priority.
    assert.equal(
        th.compare_stream_or_group_members_options(
            bob_group_item,
            admins_group_item,
            undefined,
            true,
        ),
        1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            bob_group_item,
            admins_group_item,
            undefined,
            false,
        ),
        1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            admins_group_item,
            bob_group_item,
            undefined,
            true,
        ),
        -1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(
            admins_group_item,
            bob_group_item,
            undefined,
            false,
        ),
        -1,
    );

    // Use alphabetical order to compare two users.
    assert.equal(
        th.compare_stream_or_group_members_options(b_user_1_item, b_user_2_item, undefined, true),
        -1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(b_user_1_item, b_user_2_item, undefined, false),
        -1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(b_user_2_item, b_user_1_item, undefined, true),
        1,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(b_user_2_item, b_user_1_item, undefined, false),
        1,
    );

    // Get coverage for case where two users have same names. Original order is preserved
    // in such cases.
    assert.equal(
        th.compare_stream_or_group_members_options(b_user_1_item, b_user_1_item, undefined, true),
        0,
    );
    assert.equal(
        th.compare_stream_or_group_members_options(b_user_1_item, b_user_1_item, undefined, false),
        0,
    );
});
