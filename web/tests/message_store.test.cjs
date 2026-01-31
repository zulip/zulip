"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const $ = require("./lib/zjquery.cjs");

mock_esm("../src/electron_bridge", {
    electron_bridge: {},
});

mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => true,
});

mock_esm("../src/recent_senders", {
    process_stream_message: noop,
    process_private_message: noop,
});

set_global("document", "document-stub");

const util = zrequire("util");
const people = zrequire("people");
const pm_conversations = zrequire("pm_conversations");
const message_helper = zrequire("message_helper");
const message_store = zrequire("message_store");
const message_user_ids = zrequire("message_user_ids");
const muted_users = zrequire("muted_users");
const {set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const {initialize_user_settings} = zrequire("user_settings");

set_realm(make_realm());
initialize_user_settings({user_settings: {}});

const denmark = {
    subscribed: false,
    name: "Denmark",
    stream_id: 20,
};

const devel = {
    subscribed: true,
    name: "Devel",
    stream_id: 21,
};

const me = {
    email: "me@example.com",
    user_id: 101,
    full_name: "Me Myself",
};

const alice = {
    email: "alice@example.com",
    user_id: 102,
    full_name: "Alice",
};

const bob = {
    email: "bob@example.com",
    user_id: 103,
    full_name: "Bob",
};

const cindy = {
    email: "cindy@example.com",
    user_id: 104,
    full_name: "Cindy",
};

const denise = {
    email: "denise@example.com",
    user_id: 105,
    full_name: "Denise ",
};

people.add_active_user(me);
people.add_active_user(alice);
people.add_active_user(bob);
people.add_active_user(cindy);
people.add_active_user(denise);

people.initialize_current_user(me.user_id);

function convert_recipients(people) {
    // Display_recipient uses `id` for user_ids.
    return people.map((p) => ({
        email: p.email,
        id: p.user_id,
        full_name: p.full_name,
    }));
}

function test(label, f) {
    run_test(label, (helpers) => {
        message_store.clear_for_testing();
        message_user_ids.clear_for_testing();
        f(helpers);
    });
}

test("process_new_message", ({override_rewire}) => {
    override_rewire(message_store, "save_topic_links", noop);

    let message = {
        sender_email: "me@example.com",
        sender_id: me.user_id,
        type: "private",
        display_recipient: convert_recipients([me, bob, cindy]),
        flags: ["has_alert_word"],
        is_me_message: false,
        id: 2067,
        reactions: [],
        avatar_url: `/avatar/${me.user_id}`,
    };
    message = message_helper.process_new_message({
        type: "server_message",
        raw_message: message,
    }).message;

    assert.deepEqual(message_user_ids.user_ids().toSorted(), [
        me.user_id,
        bob.user_id,
        cindy.user_id,
    ]);

    assert.equal(message.is_private, true);
    assert.equal(message.reply_to, "bob@example.com,cindy@example.com");
    assert.equal(message.to_user_ids, "103,104");
    assert.equal(message.display_reply_to, "Bob, Cindy");
    assert.equal(message.alerted, true);
    assert.equal(message.is_me_message, false);

    const retrieved_message = message_store.get(2067);
    assert.equal(retrieved_message, message);

    // access cached previous message, and test match subject/content
    message = {
        id: 2067,
        match_subject: "topic foo",
        match_content: "bar content",
        reactions: [],
        submessages: [],
        avatar_url: "/some/path/to/avatar",
    };
    message = message_helper.process_new_message({
        type: "server_message",
        raw_message: message,
    }).message;

    assert.equal(message.reply_to, "bob@example.com,cindy@example.com");
    assert.equal(message.to_user_ids, "103,104");
    assert.equal(message.display_reply_to, "Bob, Cindy");
    assert.equal(util.get_match_topic(message), "topic foo");
    assert.equal(message.match_content, "bar content");

    message = {
        sender_email: denise.email,
        sender_id: denise.user_id,
        type: "stream",
        display_recipient: "Zoolippy",
        topic: "cool thing",
        subject: "the_subject",
        id: 2068,
        reactions: [],
        avatar_url: `/avatar/${denise.user_id}`,
    };

    message = message_helper.process_new_message({
        type: "server_message",
        raw_message: message,
    }).message;
    assert.equal(message.reply_to, "denise@example.com");
    assert.deepEqual(message.flags, undefined);
    assert.equal(message.alerted, false);

    assert.deepEqual(message_user_ids.user_ids().toSorted(), [
        me.user_id,
        bob.user_id,
        cindy.user_id,
        denise.user_id,
    ]);
});

test("message_booleans_parity", () => {
    // We have two code paths that update/set message booleans.
    // This test asserts that both have identical behavior for the
    // flags common between them.
    const assert_bool_match = (flags, expected_message) => {
        let set_message = {topic: "convert_raw_message_to_message_with_booleans", flags};
        const update_message = {topic: "update_booleans"};
        set_message = message_store.convert_raw_message_to_message_with_booleans({
            type: "server_message",
            raw_message: set_message,
        }).message;
        message_store.update_booleans(update_message, flags);
        for (const key of Object.keys(expected_message)) {
            assert.equal(
                set_message[key],
                expected_message[key],
                `'${key}' != ${expected_message[key]}`,
            );
            assert.equal(update_message[key], expected_message[key]);
        }
        assert.equal(set_message.topic, "convert_raw_message_to_message_with_booleans");
        assert.equal(update_message.topic, "update_booleans");
    };

    assert_bool_match(["stream_wildcard_mentioned"], {
        mentioned: true,
        mentioned_me_directly: false,
        stream_wildcard_mentioned: true,
        topic_wildcard_mentioned: false,
        alerted: false,
    });

    assert_bool_match(["topic_wildcard_mentioned"], {
        mentioned: true,
        mentioned_me_directly: false,
        stream_wildcard_mentioned: false,
        topic_wildcard_mentioned: true,
        alerted: false,
    });

    assert_bool_match(["mentioned"], {
        mentioned: true,
        mentioned_me_directly: true,
        stream_wildcard_mentioned: false,
        topic_wildcard_mentioned: false,
        alerted: false,
    });

    assert_bool_match(["has_alert_word"], {
        mentioned: false,
        mentioned_me_directly: false,
        stream_wildcard_mentioned: false,
        topic_wildcard_mentioned: false,
        alerted: true,
    });
});

test("errors", ({disallow_rewire}) => {
    // Test a user that doesn't exist
    let message = {
        type: "private",
        display_recipient: [{id: 92714}],
    };

    blueslip.expect("error", "Unknown user_id in maybe_get_user_by_id", 1);
    blueslip.expect("error", "Unknown user id", 1); // From person.js

    // Expect each to throw two blueslip errors
    // One from message_store.ts, one from person.js
    const emails = message_store.get_pm_emails(message);
    assert.equal(emails, "?");

    assert.throws(
        () => {
            message_store.get_pm_full_names(people.pm_with_user_ids(message));
        },
        {
            name: "Error",
            message: "Unknown user_id in get_by_user_id: 92714",
        },
    );

    message = {
        type: "stream",
        display_recipient: [{}],
    };

    // This should early return and not run pm_conversations.set_partner
    disallow_rewire(pm_conversations, "set_partner");
    pm_conversations.process_message(message);
});

test("reify_message_id", () => {
    const message = {type: "private", id: 500, topic: "", queue_id: 5, draft_id: 6};

    message_store.update_message_cache({
        type: "local_message",
        message,
    });
    assert.equal(message_store.get_cached_message(500).message, message);

    message_store.reify_message_id({old_id: 500, new_id: 501});
    assert.equal(message_store.get_cached_message(500), undefined);
    assert.equal(message_store.get_cached_message(501).message, message);
    assert.deepEqual(message_store.get_cached_message(501).message, {
        type: "private",
        id: 501,
        locally_echoed: false,
    });
});

test("update_booleans", () => {
    // First, test fields that we do actually want to update.
    const message = {
        mentioned: false,
        mentioned_me_directly: false,
        stream_wildcard_mentioned: false,
        topic_wildcard_mentioned: false,
        alerted: false,
    };

    let flags = ["mentioned", "has_alert_word", "read"];
    message_store.update_booleans(message, flags);
    assert.equal(message.mentioned, true);
    assert.equal(message.mentioned_me_directly, true);
    assert.equal(message.stream_wildcard_mentioned, false);
    assert.equal(message.topic_wildcard_mentioned, false);
    assert.equal(message.alerted, true);

    flags = ["stream_wildcard_mentioned", "unread"];
    message_store.update_booleans(message, flags);
    assert.equal(message.mentioned, true);
    assert.equal(message.mentioned_me_directly, false);
    assert.equal(message.stream_wildcard_mentioned, true);
    assert.equal(message.topic_wildcard_mentioned, false);

    flags = ["topic_wildcard_mentioned", "unread"];
    message_store.update_booleans(message, flags);
    assert.equal(message.mentioned, true);
    assert.equal(message.mentioned_me_directly, false);
    assert.equal(message.stream_wildcard_mentioned, false);
    assert.equal(message.topic_wildcard_mentioned, true);

    flags = ["read"];
    message_store.update_booleans(message, flags);
    assert.equal(message.mentioned, false);
    assert.equal(message.mentioned_me_directly, false);
    assert.equal(message.alerted, false);
    assert.equal(message.stream_wildcard_mentioned, false);
    assert.equal(message.topic_wildcard_mentioned, false);

    // Make sure we don't muck with unread.
    message.unread = false;
    flags = [""];
    message_store.update_booleans(message, flags);
    assert.equal(message.unread, false);

    message.unread = true;
    flags = ["read"];
    message_store.update_booleans(message, flags);
    assert.equal(message.unread, true);
});

test("update_property", ({override_rewire}) => {
    override_rewire(message_store, "save_topic_links", noop);

    let message1 = {
        type: "stream",
        sender_full_name: alice.full_name,
        sender_id: alice.user_id,
        small_avatar_url: "alice_url",
        stream_id: devel.stream_id,
        topic: "",
        display_recipient: devel.name,
        id: 100,
        reactions: [],
        avatar_url: `/avatar/${alice.user_id}`,
        draft_id: 1,
    };
    let message2 = {
        type: "stream",
        sender_full_name: bob.full_name,
        sender_id: bob.user_id,
        small_avatar_url: "bob_url",
        stream_id: denmark.stream_id,
        topic: "",
        display_recipient: denmark.name,
        id: 101,
        reactions: [],
        avatar_url: `/avatar/${bob.user_id}`,
        draft_id: 2,
    };
    message1 = message_helper.process_new_message({
        type: "local_message",
        raw_message: message1,
    }).message;
    message2 = message_helper.process_new_message({
        type: "local_message",
        raw_message: message2,
    }).message;

    assert.equal(message1.sender_full_name, alice.full_name);
    assert.equal(message2.sender_full_name, bob.full_name);
    message_store.update_sender_full_name(bob.user_id, "Bobby");
    assert.equal(message1.sender_full_name, alice.full_name);
    assert.equal(message2.sender_full_name, "Bobby");

    assert.equal(message1.small_avatar_url, "alice_url");
    assert.equal(message2.small_avatar_url, "bob_url");
    message_store.update_small_avatar_url(bob.user_id, "bobby_url");
    assert.equal(message1.small_avatar_url, "alice_url");
    assert.equal(message2.small_avatar_url, "bobby_url");

    assert.equal(message1.stream_id, devel.stream_id);
    assert.equal(message1.display_recipient, devel.name);
    assert.equal(message2.stream_id, denmark.stream_id);
    assert.equal(message2.display_recipient, denmark.name);
    message_store.update_stream_name(devel.stream_id, "Prod");
    assert.equal(message1.stream_id, devel.stream_id);
    assert.equal(message1.display_recipient, "Prod");
    assert.equal(message2.stream_id, denmark.stream_id);
    assert.equal(message2.display_recipient, denmark.name);
});

test("remove", ({override_rewire}) => {
    override_rewire(message_store, "save_topic_links", noop);

    const message1 = {
        type: "stream",
        sender_full_name: alice.full_name,
        sender_id: alice.user_id,
        stream_id: devel.stream_id,
        stream: devel.name,
        display_recipient: devel.name,
        topic: "test",
        id: 100,
        reactions: [],
        avatar_url: `/avatar/${alice.user_id}`,
        draft_id: 1,
    };
    const message2 = {
        type: "stream",
        sender_full_name: bob.full_name,
        sender_id: bob.user_id,
        stream_id: denmark.stream_id,
        stream: denmark.name,
        display_recipient: denmark.name,
        topic: "test",
        id: 101,
        reactions: [],
        avatar_url: `/avatar/${bob.user_id}`,
        draft_id: 2,
    };
    const message3 = {
        type: "stream",
        sender_full_name: cindy.full_name,
        sender_id: cindy.user_id,
        stream_id: denmark.stream_id,
        stream: denmark.name,
        display_recipient: denmark.name,
        topic: "test",
        id: 102,
        reactions: [],
        avatar_url: `/avatar/${cindy.user_id}`,
        draft_id: 3,
    };
    for (const message of [message1, message2]) {
        message_helper.process_new_message({
            type: "local_message",
            raw_message: message,
        });
    }

    const deleted_message_ids = [message1.id, message3.id, 104];
    message_store.remove(deleted_message_ids);
    assert.equal(message_store.get(message1.id), undefined);
    assert.equal(message_store.get(message2.id).id, message2.id);
    assert.equal(message_store.get(message3.id), undefined);
});

test("get_message_ids_in_stream", ({override_rewire}) => {
    override_rewire(message_store, "save_topic_links", noop);

    const message1 = {
        type: "stream",
        sender_full_name: alice.full_name,
        sender_id: alice.user_id,
        stream_id: devel.stream_id,
        stream: devel.name,
        display_recipient: devel.name,
        topic: "test",
        id: 100,
        reactions: [],
        avatar_url: `/avatar/${alice.user_id}`,
        draft_id: 1,
    };
    const message2 = {
        sender_email: "me@example.com",
        sender_id: me.user_id,
        type: "private",
        display_recipient: convert_recipients([me, bob, cindy]),
        flags: ["has_alert_word"],
        is_me_message: false,
        id: 101,
        reactions: [],
        avatar_url: `/avatar/${me.user_id}`,
        draft_id: 2,
    };
    const message3 = {
        type: "stream",
        sender_full_name: cindy.full_name,
        sender_id: cindy.user_id,
        stream_id: denmark.stream_id,
        stream: denmark.name,
        display_recipient: denmark.name,
        topic: "test",
        id: 102,
        reactions: [],
        avatar_url: `/avatar/${cindy.user_id}`,
        draft_id: 3,
    };
    const message4 = {
        type: "stream",
        sender_full_name: me.full_name,
        sender_id: me.user_id,
        stream_id: devel.stream_id,
        stream: devel.name,
        display_recipient: devel.name,
        topic: "test",
        id: 103,
        reactions: [],
        avatar_url: `/avatar/${me.user_id}`,
        draft_id: 4,
    };

    for (const message of [message1, message2, message3, message4]) {
        message_helper.process_new_message({
            type: "local_message",
            raw_message: message,
        });
    }

    assert.deepEqual(message_store.get_message_ids_in_stream(devel.stream_id), [100, 103]);
    assert.deepEqual(message_store.get_message_ids_in_stream(denmark.stream_id), [102]);
});

function set_message_links(links) {
    $("<rewired>").set_find_results(
        "a",
        links.map((link) => ({href: link})),
    );
    $("<ignore>").set_find_results("a", []);
}

test("save_topic_links", () => {
    function assert_maps_empty() {
        assert.deepEqual(message_store.topic_links_by_to_for_testing(), new Map());
        assert.deepEqual(message_store.topic_links_by_from_for_testing(), new Map());
    }

    const message = {
        id: 5,
        type: "stream",
        stream_id: 9,
        sender_id: bob.user_id,
        topic: "worldly issues",
        content: "<rewired>",
    };

    // If the link isn't a narrow link, it doesn't save anything.
    set_message_links(["bad-link"]);
    message_store.save_topic_links(message);
    assert_maps_empty();

    // Malformed link doesn't throw an error
    set_message_links(["/#narrow/which-channel/10-design/bad-topic/hello/"]);
    message_store.save_topic_links(message);
    assert_maps_empty();

    // A message for a stream we don't know exists (including private streams)
    // doesn't save anything.
    set_message_links(["/#narrow/channel/10-design/topic/hello/"]);
    message_store.save_topic_links(message);
    assert_maps_empty();

    // If the stream does exist and we know about it, we save the data.
    stream_data.add_sub_for_tests({name: "design", subscribed: true, stream_id: 10});
    message_store.save_topic_links(message);
    assert.deepEqual(
        message_store.topic_links_by_to_for_testing(),
        new Map([[10, new Map([["hello", new Map([[0, [message.id]]])]])]]),
    );
    assert.deepEqual(
        message_store.topic_links_by_from_for_testing(),
        new Map([
            [
                message.stream_id,
                new Map([
                    [
                        message.topic,
                        new Map([
                            [
                                message.id,
                                [
                                    {
                                        stream_id: 10,
                                        topic: "hello",
                                        message_id: undefined,
                                    },
                                ],
                            ],
                        ]),
                    ],
                ]),
            ],
        ]),
    );

    message_store.clear_topic_links_for_testing();

    // A link to a message we don't know about doesn't save
    set_message_links(["/#narrow/channel/10-design/topic/hello/with/22"]);
    message_store.save_topic_links(message);
    assert_maps_empty();

    // A link to a message we do know about does save
    const linked_message = {
        id: 22,
        sender_id: alice.user_id,
        type: "stream",
        stream_id: 10,
        topic: "hello",
        content: "<ignore>",
    };
    message_store.update_message_cache({
        type: "server_message",
        message: linked_message,
    });
    message_store.save_topic_links(message);
    assert.deepEqual(
        message_store.topic_links_by_to_for_testing(),
        new Map([[10, new Map([["hello", new Map([[linked_message.id, [message.id]]])]])]]),
    );
    assert.deepEqual(
        message_store.topic_links_by_from_for_testing(),
        new Map([
            [
                message.stream_id,
                new Map([
                    [
                        message.topic,
                        new Map([
                            [
                                message.id,
                                [
                                    {
                                        stream_id: 10,
                                        topic: "hello",
                                        message_id: linked_message.id,
                                    },
                                ],
                            ],
                        ]),
                    ],
                ]),
            ],
        ]),
    );
    message_store.clear_topic_links_for_testing();

    // A link to a message from a muted user doesn't save
    muted_users.set_muted_users([{id: linked_message.sender_id}]);
    message_store.save_topic_links(message);
    assert_maps_empty();

    // A link from a message from a muted user doesn't save
    muted_users.set_muted_users([{id: message.sender_id}]);
    message_store.save_topic_links(message);
    assert_maps_empty();

    muted_users.set_muted_users([]);
});

test("get and update topic links to/from narrow", () => {
    function save_message_link(from_stream_id, from_topic, from_message_id, to_link) {
        set_message_links([to_link]);
        message_store.save_topic_links({
            id: from_message_id,
            type: "stream",
            stream_id: from_stream_id,
            sender_id: bob.user_id,
            topic: from_topic,
            content: "<rewired>",
        });
    }

    function add_message(message_id, stream_id, topic) {
        const message = {
            id: message_id,
            sender_id: alice.user_id,
            type: "stream",
            stream_id,
            topic,
            content: "<ignore>",
        };
        message_store.update_message_cache({
            type: "server_message",
            message,
        });
        return message;
    }

    const design = {name: "design", subscribed: true, stream_id: 10};
    stream_data.add_sub_for_tests(design);
    const development = {name: "development", subscribed: true, stream_id: 11};
    stream_data.add_sub_for_tests(development);
    const sales = {name: "sales", subscribed: true, stream_id: 12};
    stream_data.add_sub_for_tests(sales);

    set_message_links([]);
    const message1 = add_message(201, development.stream_id, "engineering");
    const message2 = add_message(5, design.stream_id, "goodbye");
    add_message(100, development.stream_id, "engineering");
    add_message(99, development.stream_id, "engineering");
    const message3 = add_message(3, sales.stream_id, "new client");
    add_message(400, development.stream_id, "testing");

    save_message_link(
        development.stream_id,
        "engineering",
        201,
        "/#narrow/channel/10-design/topic/goodbye/",
    );
    // Test that we ignore when the exact same data added again
    // (e.g. two links to the same narrow in the same link)
    save_message_link(
        development.stream_id,
        "engineering",
        201,
        "/#narrow/channel/10-design/topic/goodbye/",
    );
    // Save a second link from the same message to a different narrow
    save_message_link(
        development.stream_id,
        "engineering",
        201,
        "/#narrow/channel/10-design/topic/second-goodbye/",
    );
    // Save an earlier message later, this should be sorted to show up first
    // in the list of links
    save_message_link(
        development.stream_id,
        "engineering",
        100,
        "/#narrow/channel/10-design/topic/hello/",
    );
    save_message_link(
        development.stream_id,
        "testing",
        400,
        "/#narrow/channel/10-design/topic/goodbye/with/5",
    );
    // A link from the same narrow to the same narrow, but in different message.
    // This data won't show up twice in either dictionary. In "links to this narrow"
    // we only keep the first message (which will be this one).
    save_message_link(
        development.stream_id,
        "engineering",
        99,
        "/#narrow/channel/10-design/topic/hello/",
    );
    // A second link to a same narrow, from a different narrow
    save_message_link(
        sales.stream_id,
        "new client",
        3,
        "/#narrow/channel/10-design/topic/goodbye/",
    );
    // A second link to a whole stream, which will only show up in "links from" and
    // not "links to".
    save_message_link(sales.stream_id, "new client", 3, "/#narrow/channel/10-design");
    // Links from a topic to itself are ignored in both results.
    save_message_link(
        sales.stream_id,
        "new client",
        3,
        "/#narrow/channel/12-sales/topic/new.20client/",
    );
    // Unless it's linking to a specific message, then it shows up in outgoing links.
    save_message_link(
        sales.stream_id,
        "new client",
        3,
        "/#narrow/channel/12-sales/topic/new.20client/with/3",
    );

    assert.deepEqual(
        message_store.topic_links_by_to_for_testing(),
        new Map([
            [
                design.stream_id,
                new Map([
                    [
                        "goodbye",
                        new Map([
                            [0, [201, 3]],
                            [5, [400]],
                        ]),
                    ],
                    ["second-goodbye", new Map([[0, [201]]])],
                    ["hello", new Map([[0, [100, 99]]])],
                ]),
            ],
            [
                sales.stream_id,
                new Map([
                    [
                        "new client",
                        new Map([
                            [0, [3]],
                            [3, [3]],
                        ]),
                    ],
                ]),
            ],
        ]),
    );
    assert.deepEqual(
        message_store.topic_links_by_from_for_testing(),
        new Map([
            [
                sales.stream_id,
                new Map([
                    [
                        "new client",
                        new Map([
                            [
                                3,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "goodbye",
                                        message_id: undefined,
                                    },
                                    {
                                        stream_id: design.stream_id,
                                        topic: undefined,
                                        message_id: undefined,
                                    },
                                    {
                                        stream_id: sales.stream_id,
                                        topic: "new client",
                                        message_id: undefined,
                                    },
                                    {
                                        stream_id: sales.stream_id,
                                        topic: "new client",
                                        message_id: 3,
                                    },
                                ],
                            ],
                        ]),
                    ],
                ]),
            ],
            [
                development.stream_id,
                new Map([
                    [
                        "testing",
                        new Map([
                            [
                                400,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "goodbye",
                                        message_id: 5,
                                    },
                                ],
                            ],
                        ]),
                    ],
                    [
                        "engineering",
                        new Map([
                            [
                                201,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "goodbye",
                                        message_id: undefined,
                                    },
                                    {
                                        stream_id: design.stream_id,
                                        topic: "second-goodbye",
                                        message_id: undefined,
                                    },
                                ],
                            ],
                            [
                                100,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "hello",
                                        message_id: undefined,
                                    },
                                ],
                            ],
                            [
                                99,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "hello",
                                        message_id: undefined,
                                    },
                                ],
                            ],
                        ]),
                    ],
                ]),
            ],
        ]),
    );

    // Test empty cases.
    assert.deepEqual(
        message_store.topic_links_from_narrow(development.stream_id, "nothing here"),
        [],
    );

    assert.deepEqual(
        message_store.topic_links_to_narrow(development.stream_id, "nothing here"),
        [],
    );

    // Testing that:
    // * The two hello links are deduplicated, so we only see one of them.
    // * We sort the data by message id, so message 99 to "hello" is listed before message
    //   201 to goodbye and second-goodbye, even though we added the "hello" link after.
    assert.deepEqual(message_store.topic_links_from_narrow(development.stream_id, "engineering"), [
        {
            text: "#design > hello",
            url: "#narrow/channel/10-design/topic/hello",
        },
        {
            text: "#design > goodbye",
            url: "#narrow/channel/10-design/topic/goodbye",
        },
        {
            text: "#design > second-goodbye",
            url: "#narrow/channel/10-design/topic/second-goodbye",
        },
    ]);

    // Links in messages 99 and 100 are deduplicated since they are the same link,
    // and we only show message 99 since it occurs first.
    assert.deepEqual(message_store.topic_links_to_narrow(design.stream_id, "hello"), [
        {
            text: "#development > engineering @ 💬",
            url: "#narrow/channel/11-development/topic/engineering/near/99",
        },
    ]);

    // Links are sorted by message id even though the earlier message
    // was added after the later message.
    assert.deepEqual(message_store.topic_links_to_narrow(design.stream_id, "goodbye"), [
        {
            text: "#sales > new client @ 💬",
            url: "#narrow/channel/12-sales/topic/new.20client/near/3",
        },
        {
            text: "#development > engineering @ 💬",
            url: "#narrow/channel/11-development/topic/engineering/near/201",
        },
        {
            text: "#development > testing @ 💬",
            url: "#narrow/channel/11-development/topic/testing/near/400",
        },
    ]);

    // Links from sales to sales don't show up in either list, except
    // the link to a specific message which shows up in outgoing links
    assert.deepEqual(message_store.topic_links_from_narrow(sales.stream_id, "new client"), [
        {
            text: "#design > goodbye",
            url: "#narrow/channel/10-design/topic/goodbye",
        },
        {
            text: "#design",
            url: "#narrow/channel/10-design",
        },
        {
            text: "#sales > new client @ 💬",
            url: "#narrow/channel/12-sales/topic/new.20client/near/3",
        },
    ]);
    assert.deepEqual(message_store.topic_links_to_narrow(sales.stream_id, "new client"), []);

    // TOPIC EDIT
    assert.equal(message1.id, 201);
    assert.equal(message1.stream_id, development.stream_id);
    assert.equal(message1.topic, "engineering");
    message_store.process_topic_edit({
        message_ids: [201],
        new_stream_id: sales.stream_id,
        new_topic: "super engineering",
    });
    message1.stream_id = sales.stream_id;
    message1.topic = "super engineering";
    assert.deepEqual(message_store.topic_links_to_narrow(design.stream_id, "goodbye"), [
        {
            text: "#sales > new client @ 💬",
            url: "#narrow/channel/12-sales/topic/new.20client/near/3",
        },
        // This now links to the new stream and topic for message 201
        {
            text: "#sales > super engineering @ 💬",
            url: "#narrow/channel/12-sales/topic/super.20engineering/near/201",
        },
        {
            text: "#development > testing @ 💬",
            url: "#narrow/channel/11-development/topic/testing/near/400",
        },
    ]);

    assert.equal(message2.id, 5);
    assert.equal(message2.stream_id, design.stream_id);
    assert.equal(message2.topic, "goodbye");
    message_store.process_topic_edit({
        message_ids: [5],
        new_stream_id: sales.stream_id,
        new_topic: "signing off",
    });
    message2.stream_id = sales.stream_id;
    message2.topic = "signing off";
    assert.deepEqual(
        message_store.topic_links_to_narrow(design.stream_id, "goodbye"),
        // These are links to the old narrow still present from other messages
        [
            {
                text: "#sales > new client @ 💬",
                url: "#narrow/channel/12-sales/topic/new.20client/near/3",
            },
            {
                text: "#sales > super engineering @ 💬",
                url: "#narrow/channel/12-sales/topic/super.20engineering/near/201",
            },
        ],
    );
    assert.deepEqual(message_store.topic_links_to_narrow(sales.stream_id, "signing off"), [
        {
            // This link from the moved message now links to the new topic
            text: "#development > testing @ 💬",
            url: "#narrow/channel/11-development/topic/testing/near/400",
        },
    ]);

    assert.equal(message3.id, 3);
    assert.equal(message3.stream_id, sales.stream_id);
    assert.equal(message3.topic, "new client");
    message_store.process_topic_edit({
        message_ids: [3],
        new_stream_id: design.stream_id,
        new_topic: "client logo",
    });
    message3.stream_id = design.stream_id;
    message3.topic = "client logo";
    assert.deepEqual(message_store.topic_links_from_narrow(sales.stream_id, "new client"), []);
    assert.deepEqual(message_store.topic_links_from_narrow(design.stream_id, "client logo"), [
        {
            text: "#design > goodbye",
            url: "#narrow/channel/10-design/topic/goodbye",
        },
        {
            text: "#design",
            url: "#narrow/channel/10-design",
        },
        // This one doesn't change because it's a link to the topic (and not any moved
        // message), so it still links to the old topic, though now from the moved
        // message in the new topic. (Note it didn't show up before because it was
        // a link to the same topic, but now it does show up because it's a link to
        // a different topic.)
        {
            text: "#sales > new client",
            url: "#narrow/channel/12-sales/topic/new.20client",
        },
        // This one changes because it links to a specific message id, now associated
        // with a new narrow.
        {
            text: "#design > client logo @ 💬",
            url: "#narrow/channel/10-design/topic/client.20logo/near/3",
        },
    ]);

    // MESSAGE ID UPDATE
    message_store.reify_message_id({old_id: 3, new_id: 33});
    assert.deepEqual(message_store.topic_links_from_narrow(design.stream_id, "client logo"), [
        {
            text: "#design > goodbye",
            url: "#narrow/channel/10-design/topic/goodbye",
        },
        {
            text: "#design",
            url: "#narrow/channel/10-design",
        },
        {
            text: "#sales > new client",
            url: "#narrow/channel/12-sales/topic/new.20client",
        },
        // Testing that 3 -> 33
        {
            text: "#design > client logo @ 💬",
            url: "#narrow/channel/10-design/topic/client.20logo/near/33",
        },
    ]);

    // REMOVE MESSAGE
    message_store.remove([33]);
    assert.deepEqual(message_store.topic_links_from_narrow(design.stream_id, "client logo"), []);
});
