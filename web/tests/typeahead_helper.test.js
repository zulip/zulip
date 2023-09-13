"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const {page_params, user_settings} = require("./lib/zpage_params");

const stream_topic_history = mock_esm("../src/stream_topic_history");

const settings_config = zrequire("settings_config");
const pm_conversations = zrequire("pm_conversations");

const recent_senders = zrequire("recent_senders");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const stream_list_sort = zrequire("stream_list_sort");
const compose_state = zrequire("compose_state");
const emoji = zrequire("emoji");
const pygments_data = zrequire("../generated/pygments_data.json");
const util = zrequire("util");
const actual_pygments_data = {...pygments_data};
const ct = zrequire("composebox_typeahead");
const th = zrequire("typeahead_helper");

let next_id = 0;

function assertSameEmails(lst1, lst2) {
    assert.deepEqual(
        lst1.map((r) => r.email),
        lst2.map((r) => r.email),
    );
}

const a_bot = {
    email: "a_bot@zulip.com",
    full_name: "A Zulip test bot",
    is_admin: false,
    is_bot: true,
    user_id: 1,
};

const a_user = {
    email: "a_user@zulip.org",
    full_name: "A Zulip user",
    is_admin: false,
    is_bot: false,
    user_id: 2,
};

const b_user_1 = {
    email: "b_user_1@zulip.net",
    full_name: "Bob 1",
    is_admin: false,
    is_bot: false,
    user_id: 3,
};

const b_user_2 = {
    email: "b_user_2@zulip.net",
    full_name: "Bob 2",
    is_admin: true,
    is_bot: false,
    user_id: 4,
};

const b_user_3 = {
    email: "b_user_3@zulip.net",
    full_name: "Bob 3",
    is_admin: false,
    is_bot: false,
    user_id: 5,
};

const b_bot = {
    email: "b_bot@example.com",
    full_name: "B bot",
    is_admin: false,
    is_bot: true,
    user_id: 6,
};

const zman = {
    email: "zman@test.net",
    full_name: "Zman",
    is_admin: false,
    is_bot: false,
    user_id: 7,
};

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

function test(label, f) {
    run_test(label, (helpers) => {
        pm_conversations.clear_for_testing();
        recent_senders.clear_for_testing();
        peer_data.clear_for_testing();
        people.clear_recipient_counts_for_testing();
        page_params.is_admin = false;
        page_params.realm_is_zephyr_mirror_realm = false;

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
        },
        {
            stream_id: 102,
            name: "Docs",
            pin_to_top: false,
            stream_weekly_traffic: 100,
            subscribed: true,
        },
        {
            stream_id: 103,
            name: "Derp",
            pin_to_top: false,
            stream_weekly_traffic: 0,
            subscribed: true,
        },
        {
            stream_id: 104,
            name: "Denmark",
            pin_to_top: true,
            stream_weekly_traffic: 100,
            subscribed: true,
        },
        {
            stream_id: 105,
            name: "dead",
            pin_to_top: false,
            stream_weekly_traffic: 0,
            subscribed: true,
        },
    ];

    override(
        user_settings,
        "demote_inactive_streams",
        settings_config.demote_inactive_streams_values.always.code,
    );

    stream_list_sort.set_filter_out_inactives();
    override(
        stream_topic_history,
        "stream_has_topics",
        (stream_id) => ![105, 205].includes(stream_id),
    );

    test_streams = th.sort_streams(test_streams, "d");
    assert.deepEqual(test_streams[0].name, "Denmark"); // Pinned streams first
    assert.deepEqual(test_streams[1].name, "Docs"); // Active streams next
    assert.deepEqual(test_streams[2].name, "Derp"); // Less subscribers
    assert.deepEqual(test_streams[3].name, "Dev"); // Alphabetically last
    assert.deepEqual(test_streams[4].name, "dead"); // Inactive streams last

    // Test sort streams with description
    test_streams = [
        {
            stream_id: 201,
            name: "Dev",
            description: "development help",
            subscribed: true,
        },
        {
            stream_id: 202,
            name: "Docs",
            description: "writing docs",
            subscribed: true,
        },
        {
            stream_id: 203,
            name: "Derp",
            description: "derping around",
            subscribed: true,
        },
        {
            stream_id: 204,
            name: "Denmark",
            description: "visiting Denmark",
            subscribed: true,
        },
        {
            stream_id: 205,
            name: "dead",
            description: "dead stream",
            subscribed: true,
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

test("sort_languages", () => {
    Object.assign(pygments_data, {
        langs: {
            python: {priority: 26},
            javascript: {priority: 27},
            php: {priority: 16},
            pascal: {priority: 15},
            perl: {priority: 3},
            css: {priority: 21},
        },
    });

    let test_langs = ["pascal", "perl", "php", "python", "javascript"];
    test_langs = th.sort_languages(test_langs, "p");

    // Sort languages by matching first letter, and then by popularity
    assert.deepEqual(test_langs, ["python", "php", "pascal", "perl", "javascript"]);

    // Test if popularity between two languages are the same
    pygments_data.langs.php = {priority: 26};
    test_langs = ["pascal", "perl", "php", "python", "javascript"];
    test_langs = th.sort_languages(test_langs, "p");

    assert.deepEqual(test_langs, ["php", "python", "pascal", "perl", "javascript"]);

    // Some final tests on the actual pygments data to check ordering.
    //
    // We may eventually want to use human-readable names like
    // "JavaScript" with several machine-readable aliases for what the
    // user typed, which might help provide a better user experience.
    Object.assign(pygments_data, actual_pygments_data);
    test_langs = ["j", "java", "javascript", "js"];

    // Sort according to priority only.
    test_langs = th.sort_languages(test_langs, "jav");
    assert.deepEqual(test_langs, ["javascript", "java", "j"]);

    // Push exact matches to top, regardless of priority
    test_langs = th.sort_languages(test_langs, "java");
    assert.deepEqual(test_langs, ["java", "javascript", "j"]);
    test_langs = th.sort_languages(test_langs, "j");
    assert.deepEqual(test_langs, ["j", "javascript", "java"]);

    // (Only one alias should be shown per language
    // (i.e searching for "js" shouldn't show "javascript")
    test_langs = ["js", "javascript", "java"];
    test_langs = th.sort_languages(test_langs, "js");
    assert.deepEqual(test_langs, ["js", "java"]);
});

function get_typeahead_result(query, current_stream_id, current_topic) {
    const result = th.sort_recipients({
        users: people.get_realm_users(),
        query,
        current_stream_id,
        current_topic,
    });
    return result.map((person) => person.email);
}

test("sort_recipients", () => {
    // Typeahead for recipientbox [query, "", undefined]
    assert.deepEqual(get_typeahead_result("b", ""), [
        "b_user_1@zulip.net",
        "b_user_2@zulip.net",
        "b_user_3@zulip.net",
        "b_bot@example.com",
        "a_user@zulip.org",
        "zman@test.net",
        "a_bot@zulip.com",
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
        subscriber_email_3,
        subscriber_email_2,
        subscriber_email_1,
        "b_user_1@zulip.net",
        "zman@test.net",
        "a_user@zulip.org",
        "a_bot@zulip.com",
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
        "b_bot@example.com",
        "a_bot@zulip.com",
        "b_user_1@zulip.net",
        "b_user_2@zulip.net",
    ]);
});

test("sort_recipients all mention", () => {
    compose_state.set_message_type("stream");
    const all_obj = ct.broadcast_mentions()[0];
    assert.equal(all_obj.email, "all");
    assert.equal(all_obj.is_broadcast, true);
    assert.equal(all_obj.idx, 0);

    // Test person email is "all" or "everyone"
    const test_objs = [...matches, all_obj];

    const results = th.sort_recipients({
        users: test_objs,
        query: "a",
        current_stream_id: linux_sub.stream_id,
        current_topic: "Linux topic",
    });

    assertSameEmails(results, [all_obj, a_bot, a_user, b_user_1, b_user_2, b_user_3, b_bot, zman]);
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
        "b_bot@example.com",
        "b_user_3@zulip.net",
        "a_bot@zulip.com",
        "a_user@zulip.org",
        "zman@test.net",
    ]);

    // Now prioritize stream membership over pm counts.
    peer_data.add_subscriber(linux_sub.stream_id, b_user_3.user_id);

    assert.deepEqual(get_typeahead_result("b", linux_sub.stream_id, "Linux topic"), [
        "b_user_3@zulip.net",
        "b_user_1@zulip.net",
        "b_user_2@zulip.net",
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
        th.compare_people_for_relevance(b_user_1, b_user_3, compare, linux_sub.stream_id),
        1,
    );
    assert.equal(
        th.compare_people_for_relevance(b_user_3, b_user_1, compare, linux_sub.stream_id),
        -1,
    );
});

test("sort_recipients dup bots", () => {
    const dup_objects = [...matches, a_bot];

    const recipients = th.sort_recipients({
        users: dup_objects,
        query: "b",
        current_stream_id: "",
        current_topic: "",
    });
    const recipients_email = recipients.map((person) => person.email);
    const expected = [
        "b_user_1@zulip.net",
        "b_user_2@zulip.net",
        "b_user_3@zulip.net",
        "b_bot@example.com",
        "a_user@zulip.org",
        "zman@test.net",
        "a_bot@zulip.com",
        "a_bot@zulip.com",
    ];
    assert.deepEqual(recipients_email, expected);
});

test("sort_recipients dup alls", () => {
    compose_state.set_message_type("stream");
    const all_obj = ct.broadcast_mentions()[0];

    // full_name starts with same character but emails are 'all'
    const test_objs = [all_obj, a_user, all_obj];

    const recipients = th.sort_recipients({
        users: test_objs,
        query: "a",
        current_stream_id: linux_sub.stream_id,
        current_topic: "Linux topic",
    });

    const expected = [all_obj, a_user];
    assertSameEmails(recipients, expected);
});

test("sort_recipients dup alls direct message", () => {
    compose_state.set_message_type("private");
    const all_obj = ct.broadcast_mentions()[0];

    // full_name starts with same character but emails are 'all'
    const test_objs = [all_obj, a_user, all_obj];

    const recipients = th.sort_recipients({
        users: test_objs,
        query: "a",
    });

    const expected = [a_user, all_obj];
    assertSameEmails(recipients, expected);
});

test("sort_recipients subscribers", () => {
    // b_user_2 is a subscriber and b_user_1 is not.
    const small_matches = [b_user_2, b_user_1];
    const recipients = th.sort_recipients({
        users: small_matches,
        query: "b",
        current_stream_id: dev_sub.stream_id,
        current_topic: "Dev topic",
    });
    const recipients_email = recipients.map((person) => person.email);
    const expected = ["b_user_2@zulip.net", "b_user_1@zulip.net"];
    assert.deepEqual(recipients_email, expected);
});

test("sort_recipients pm partners", () => {
    // b_user_3 is a pm partner and b_user_2 is not and
    // both are not subscribed to the stream Linux.
    const small_matches = [b_user_3, b_user_2];
    const recipients = th.sort_recipients({
        users: small_matches,
        query: "b",
        current_stream_id: linux_sub.stream_id,
        current_topic: "Linux topic",
    });
    const recipients_email = recipients.map((person) => person.email);
    const expected = ["b_user_3@zulip.net", "b_user_2@zulip.net"];
    assert.deepEqual(recipients_email, expected);
});

test("sort broadcast mentions for stream message type", () => {
    // test the normal case, which is that the
    // broadcast mentions are already sorted (we
    // actually had a bug where the sort would
    // randomly rearrange them)
    compose_state.set_message_type("stream");
    const results = th.sort_people_for_relevance(ct.broadcast_mentions().reverse(), "", "");

    assert.deepEqual(
        results.map((r) => r.email),
        ["all", "everyone", "stream"],
    );

    // Reverse the list to test actual sorting
    // and ensure test coverage for the defensive
    // code.  Also, add in some people users.
    const test_objs = [...ct.broadcast_mentions()].reverse();
    test_objs.unshift(zman);
    test_objs.push(a_user);

    const results2 = th.sort_people_for_relevance(test_objs, "", "");

    assert.deepEqual(
        results2.map((r) => r.email),
        ["all", "everyone", "stream", a_user.email, zman.email],
    );
});

test("sort broadcast mentions for direct message type", () => {
    compose_state.set_message_type("private");
    const results = th.sort_people_for_relevance(ct.broadcast_mentions().reverse(), "", "");

    assert.deepEqual(
        results.map((r) => r.email),
        ["all", "everyone"],
    );

    const test_objs = [...ct.broadcast_mentions()].reverse();
    test_objs.unshift(zman);
    test_objs.push(a_user);

    const results2 = th.sort_people_for_relevance(test_objs, "", "");

    assert.deepEqual(
        results2.map((r) => r.email),
        [a_user.email, zman.email, "all", "everyone"],
    );
});

test("test compare directly for stream message type", () => {
    // This is important for ensuring test coverage.
    // We don't technically need it now, but our test
    // coverage is subject to the whims of how JS sorts.
    compose_state.set_message_type("stream");
    const all_obj = ct.broadcast_mentions()[0];

    assert.equal(th.compare_people_for_relevance(all_obj, all_obj), 0);
    assert.equal(th.compare_people_for_relevance(all_obj, zman), -1);
    assert.equal(th.compare_people_for_relevance(zman, all_obj), 1);
});

test("test compare directly for direct message", () => {
    compose_state.set_message_type("private");
    const all_obj = ct.broadcast_mentions()[0];

    assert.equal(th.compare_people_for_relevance(all_obj, all_obj), 0);
    assert.equal(th.compare_people_for_relevance(all_obj, zman), 1);
    assert.equal(th.compare_people_for_relevance(zman, all_obj), -1);
});

test("highlight_with_escaping", () => {
    function highlight(query, item) {
        const regex = th.build_highlight_regex(query);
        return th.highlight_with_escaping_and_regex(regex, item);
    }

    let item = "Denmark";
    let query = "Den";
    let expected = "<strong>Den</strong>mark";
    let result = highlight(query, item);
    assert.equal(result, expected);

    item = "w3IrD_naMe";
    query = "w3IrD_naMe";
    expected = "<strong>w3IrD_naMe</strong>";
    result = highlight(query, item);
    assert.equal(result, expected);

    item = "development help";
    query = "development h";
    expected = "<strong>development h</strong>elp";
    result = highlight(query, item);
    assert.equal(result, expected);
});

test("render_person when emails hidden", ({mock_template}) => {
    // Test render_person with regular person, under hidden email visibility case
    let rendered = false;
    mock_template("typeahead_list_item.hbs", false, (args) => {
        assert.equal(args.primary, b_user_1.full_name);
        assert.equal(args.secondary, undefined);
        rendered = true;
        return "typeahead-item-stub";
    });
    assert.equal(th.render_person(b_user_1), "typeahead-item-stub");
    assert.ok(rendered);
});

test("render_person", ({mock_template}) => {
    // Test render_person with regular person
    a_user.delivery_email = "a_user_delivery@zulip.org";
    let rendered = false;
    mock_template("typeahead_list_item.hbs", false, (args) => {
        assert.equal(args.primary, a_user.full_name);
        assert.equal(args.secondary, a_user.delivery_email);
        rendered = true;
        return "typeahead-item-stub";
    });
    assert.equal(th.render_person(a_user), "typeahead-item-stub");
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
    assert.equal(th.render_person(special_person), "typeahead-item-stub");
    assert.ok(rendered);
});

test("render_stream", ({mock_template}) => {
    // Test render_stream with short description
    let rendered = false;
    const stream = {
        description: "This is a short description.",
        stream_id: 42,
        name: "Short description",
    };

    mock_template("typeahead_list_item.hbs", false, (args) => {
        assert.equal(args.stream, stream);
        assert.equal(args.secondary, stream.description);
        rendered = true;
        return "typeahead-item-stub";
    });
    assert.equal(th.render_stream(stream), "typeahead-item-stub");
    assert.ok(rendered);
});

test("render_stream w/long description", ({mock_template}) => {
    // Test render_stream with long description
    let rendered = false;
    const stream = {
        description: "This is a very very very very very long description.",
        stream_id: 43,
        name: "Long description",
    };

    mock_template("typeahead_list_item.hbs", false, (args) => {
        assert.equal(args.stream, stream);
        const short_desc = stream.description.slice(0, 35);
        assert.equal(args.secondary, short_desc + "...");
        rendered = true;
        return "typeahead-item-stub";
    });
    assert.equal(th.render_stream(stream), "typeahead-item-stub");
    assert.ok(rendered);
});

test("render_emoji", ({mock_template}) => {
    // Test render_emoji with normal emoji.
    let expected_template_data = {
        primary: "thumbs up",
        emoji_code: "1f44d",
        is_emoji: true,
        has_image: false,
        has_secondary: false,
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
        has_secondary: false,
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
    assert.equal(actual_pygments_data.langs.custom_a, undefined);
    assert.equal(actual_pygments_data.langs.custom_b, undefined);
    // Since custom_a has no popularity score, it gets sorted behind python.
    assert.equal(th.compare_language("custom_a", "python"), 1);
    assert.equal(th.compare_language("python", "custom_a"), -1);
    // Whenever there is a tie, even in the case neither have a popularity
    // score, then alphabetical order is used to break the tie.
    assert.equal(th.compare_language("custom_a", "custom_b"), util.strcmp("custom_a", "custom_b"));
});
