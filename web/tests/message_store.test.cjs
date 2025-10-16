"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_stream} = require("./lib/example_stream.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

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

const denmark = make_stream({
    subscribed: false,
    name: "Denmark",
    stream_id: 20,
});

const devel = make_stream({
    subscribed: true,
    name: "Devel",
    stream_id: 21,
});
stream_data.add_sub_for_tests(denmark);
stream_data.add_sub_for_tests(devel);

const me = make_user({
    email: "me@example.com",
    user_id: 101,
    full_name: "Me Myself",
});

const alice = make_user({
    email: "alice@example.com",
    user_id: 102,
    full_name: "Alice",
});

const bob = make_user({
    email: "bob@example.com",
    user_id: 103,
    full_name: "Bob",
});

const cindy = make_user({
    email: "cindy@example.com",
    user_id: 104,
    full_name: "Cindy",
});

const denise = make_user({
    email: "denise@example.com",
    user_id: 105,
    full_name: "Denise ",
});

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

test("process_new_message", () => {
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
        submessages: [],
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
        submessages: [],
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

test("update_property", () => {
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

test("remove", () => {
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

test("get_message_ids_in_stream", () => {
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

test("maybe_update_raw_content", () => {
    const message1 = {
        id: 1,
        raw_content: undefined,
        type: "stream",
        stream: devel.name,
        stream_id: devel.stream_id,
    };

    const message2 = {
        id: 2,
        raw_content: undefined,
        type: "stream",
        stream: denmark.name,
        stream_id: denmark.stream_id,
    };

    const message3 = {
        id: 3,
        raw_content: "should be reset",
        type: "stream",
        stream: denmark.name,
        stream_id: denmark.stream_id,
    };
    for (const message of [message1, message2, message3]) {
        message_store.update_message_cache({message});
    }
    message_store.maybe_update_raw_content(message1.id, "hello world");
    message_store.maybe_update_raw_content(message2.id, "hello world");
    message_store.maybe_update_raw_content(message3.id, "hello world");
    // It is safe to update raw_content of messages
    // we will be receiving events for.
    assert.equal(message1.raw_content, "hello world");
    // It is not safe to update raw_content of messages
    // we won't be receiving events for.
    assert.equal(message2.raw_content, undefined);
    // We should reset accidentally cached raw_content for messages
    // we don't receive update events for.
    assert.equal(message3.raw_content, undefined);

    // Deleting a message from the message store, should
    // no longer update the raw_content of the message
    // object.
    message_store.remove([1]);
    message_store.maybe_update_raw_content(message1.id, "bye world");
    assert.equal(message1.raw_content, "hello world");
});

test("save_topic_links", () => {
    function assert_maps_empty() {
        assert.deepEqual(message_store.topic_links_by_to_for_testing(), new Map());
        assert.deepEqual(message_store.topic_links_by_from_for_testing(), new Map());
    }

    function message_with_content(content) {
        return {
            id: 5,
            type: "stream",
            stream_id: 9,
            sender_id: bob.user_id,
            topic: "worldly issues",
            content,
        };
    }

    // If the link isn't a narrow link, it doesn't save anything.
    let link = "bad-link";
    message_store.save_topic_links(message_with_content(`<div><a href='${link}'>a link!</a>`));
    assert_maps_empty();

    // Malformed link doesn't throw an error
    link = "/#narrow/which-channel/10-design/bad-topic/hello/";
    message_store.save_topic_links(message_with_content(`<div><a href='${link}'>a link!</a>`));
    assert_maps_empty();

    // A message for a stream we don't know exists (including private streams)
    // doesn't save anything.
    link = "/#narrow/channel/10-design/topic/hello/";
    message_store.save_topic_links(message_with_content(`<div><a href='${link}'>a link!</a>`));
    assert_maps_empty();

    // If the stream does exist and we know about it, we save the data.
    stream_data.add_sub_for_tests({name: "design", subscribed: true, stream_id: 10});
    let message = message_with_content(`<div><a href='${link}'>a link!</a>`);
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
    link = "/#narrow/channel/10-design/topic/hello/near/22";
    message = message_with_content(`<div><a href='${link}'>a link!</a>`);
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
        if (from_message_id) {
            const from_message = message_store.get(from_message_id);
            assert.ok(from_message !== undefined);
            assert.ok(from_message.stream_id === from_stream_id);
            assert.ok(from_message.topic === from_topic);
        }
        message_store.save_topic_links({
            id: from_message_id,
            type: "stream",
            stream_id: from_stream_id,
            sender_id: bob.user_id,
            topic: from_topic,
            content: `<div><a href='${to_link}'>a link!</a>`,
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

    // set_message_links([]);
    const message1 = add_message(201, development.stream_id, "engineering");
    const message2 = add_message(5, design.stream_id, "goodbye");
    const message3 = add_message(100, development.stream_id, "engineering");
    const message4 = add_message(99, development.stream_id, "engineering");
    const message5 = add_message(3, sales.stream_id, "new client");
    const message6 = add_message(20, sales.stream_id, "new client");
    const message7 = add_message(400, development.stream_id, "testing");
    const NO_MESSAGE_ID = 0;

    // Save a link from a message in #development>engineering
    save_message_link(
        development.stream_id,
        "engineering",
        message1.id,
        "/#narrow/channel/10-design/topic/goodbye/",
    );
    // Test that we ignore when the exact same data added again
    // (e.g. two links to the same narrow in the same message)
    save_message_link(
        development.stream_id,
        "engineering",
        message1.id,
        "/#narrow/channel/10-design/topic/goodbye/",
    );
    assert.deepEqual(
        message_store.topic_links_by_to_for_testing(),
        new Map([
            [design.stream_id, new Map([["goodbye", new Map([[NO_MESSAGE_ID, [message1.id]]])]])],
        ]),
    );
    assert.deepEqual(
        message_store.topic_links_by_from_for_testing(),
        new Map([
            [
                development.stream_id,
                new Map([
                    [
                        "engineering",
                        new Map([
                            [
                                message1.id,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "goodbye",
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

    // Save a second link *to* the same narrow, but *from* a different narrow
    save_message_link(
        sales.stream_id,
        "new client",
        message5.id,
        "/#narrow/channel/10-design/topic/goodbye/",
    );
    // Save a second link *from* the same message, but *to* a different narrow
    save_message_link(
        development.stream_id,
        "engineering",
        message1.id,
        "/#narrow/channel/10-design/topic/second-goodbye/",
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
                            // from message5 is new
                            [NO_MESSAGE_ID, [message1.id, message5.id]],
                        ]),
                    ],
                    // to "second-goodbye" is new
                    ["second-goodbye", new Map([[NO_MESSAGE_ID, [message1.id]]])],
                ]),
            ],
        ]),
    );
    assert.deepEqual(
        message_store.topic_links_by_from_for_testing(),
        new Map([
            [
                development.stream_id,
                new Map([
                    [
                        "engineering",
                        new Map([
                            [
                                message1.id,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "goodbye",
                                        message_id: undefined,
                                    },
                                    // to "second-goodbye" is new
                                    {
                                        stream_id: design.stream_id,
                                        topic: "second-goodbye",
                                        message_id: undefined,
                                    },
                                ],
                            ],
                        ]),
                    ],
                ]),
            ],
            // from sales is new
            [
                sales.stream_id,
                new Map([
                    [
                        "new client",
                        new Map([
                            [
                                message5.id,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "goodbye",
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

    // Save a link from an earlier message in #development (smaller id). Even though
    // we saved the later message first, this should be sorted to show up first in
    // the list of outgoing links.
    assert.ok(message3.id < message1.id);
    save_message_link(
        development.stream_id,
        "engineering",
        message3.id,
        "/#narrow/channel/10-design/topic/hello/",
    );
    assert.deepEqual(
        message_store.topic_links_by_to_for_testing(),
        new Map([
            [
                design.stream_id,
                new Map([
                    // Link to "hello" is new and earlier
                    ["hello", new Map([[NO_MESSAGE_ID, [message3.id]]])],
                    ["goodbye", new Map([[NO_MESSAGE_ID, [message1.id, message5.id]]])],
                    ["second-goodbye", new Map([[NO_MESSAGE_ID, [message1.id]]])],
                ]),
            ],
        ]),
    );
    assert.deepEqual(
        message_store.topic_links_by_from_for_testing(),
        new Map([
            [
                development.stream_id,
                new Map([
                    [
                        "engineering",
                        new Map([
                            // message3 is new and earlier
                            [
                                message3.id,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "hello",
                                        message_id: undefined,
                                    },
                                ],
                            ],
                            [
                                message1.id,
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
                        ]),
                    ],
                ]),
            ],
            [
                sales.stream_id,
                new Map([
                    [
                        "new client",
                        new Map([
                            [
                                message5.id,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "goodbye",
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

    // A link from the same narrow to the same narrow, but in a different message.
    // In links to this narrow we only keep the message with the smaller/earlier id
    // (which will be this one). In links from this narrow, we show the link only
    // once even though it's linked from multiple messages. But the high level topic
    // maps will have data from both messages.
    assert.deepEqual(message_store.topic_links_to_narrow(design.stream_id, "hello"), [
        {
            text: "#development > engineering @ 💬",
            url: `#narrow/channel/11-development/topic/engineering/near/${message3.id}`,
        },
    ]);
    // There are currently three links from #development>engineering
    assert.equal(
        message_store.topic_links_from_narrow(development.stream_id, "engineering").length,
        3,
    );
    // Now save an earlier message with the same link
    assert.ok(message4.id < message3.id);
    save_message_link(
        development.stream_id,
        "engineering",
        message4.id,
        "/#narrow/channel/10-design/topic/hello/",
    );
    // Now only message4 will show up, since it occurs first.
    assert.deepEqual(message_store.topic_links_to_narrow(design.stream_id, "hello"), [
        {
            text: "#development > engineering @ 💬",
            url: `#narrow/channel/11-development/topic/engineering/near/${message4.id}`,
        },
    ]);
    // * There are still only three links from #development>engineering, since message4's
    //   "hello" link was redundant.
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

    // The high level topic maps will have data from both messages.
    assert.deepEqual(
        message_store.topic_links_by_to_for_testing(),
        new Map([
            [
                design.stream_id,
                new Map([
                    [
                        "hello",
                        new Map([
                            // message4 is new
                            [NO_MESSAGE_ID, [message3.id, message4.id]],
                        ]),
                    ],
                    ["goodbye", new Map([[NO_MESSAGE_ID, [message1.id, message5.id]]])],
                    ["second-goodbye", new Map([[NO_MESSAGE_ID, [message1.id]]])],
                ]),
            ],
        ]),
    );
    assert.deepEqual(
        message_store.topic_links_by_from_for_testing(),
        new Map([
            [
                development.stream_id,
                new Map([
                    [
                        "engineering",
                        new Map([
                            [
                                message3.id,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "hello",
                                        message_id: undefined,
                                    },
                                ],
                            ],
                            [
                                message1.id,
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
                            // message4 is new
                            [
                                message4.id,
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
            [
                sales.stream_id,
                new Map([
                    [
                        "new client",
                        new Map([
                            [
                                message5.id,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "goodbye",
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

    // Save a link to a specific message.
    save_message_link(
        development.stream_id,
        "testing",
        message7.id,
        "/#narrow/channel/10-design/topic/goodbye/near/5",
    );
    // A link to a whole stream, which will only show up in "links from" and
    // not "links to" (since it isn't a link to a topic).
    save_message_link(sales.stream_id, "new client", message5.id, "/#narrow/channel/10-design");
    // Links from a topic to itself are ignored when we fetch to/from links for a narrow,
    // but we still save them in case those messages are moved later (and, in a new narrow,
    // could stop being a link from a narrrow to itself).
    save_message_link(
        sales.stream_id,
        "new client",
        message5.id,
        "/#narrow/channel/12-sales/topic/new.20client/",
    );
    save_message_link(
        sales.stream_id,
        "new client",
        message6.id,
        `/#narrow/channel/12-sales/topic/new.20client/near/${message5.id}`,
    );

    assert.deepEqual(
        message_store.topic_links_by_to_for_testing(),
        new Map([
            [
                design.stream_id,
                new Map([
                    ["hello", new Map([[NO_MESSAGE_ID, [message3.id, message4.id]]])],
                    [
                        "goodbye",
                        new Map([
                            [NO_MESSAGE_ID, [message1.id, message5.id]],
                            // This link to a specific message is new
                            [5, [message7.id]],
                        ]),
                    ],
                    ["second-goodbye", new Map([[NO_MESSAGE_ID, [message1.id]]])],
                ]),
            ],
            // The links to sales are new
            [
                sales.stream_id,
                new Map([
                    [
                        "new client",
                        new Map([
                            [NO_MESSAGE_ID, [message5.id]],
                            [message5.id, [message6.id]],
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
                development.stream_id,
                new Map([
                    [
                        "engineering",
                        new Map([
                            [
                                message3.id,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "hello",
                                        message_id: undefined,
                                    },
                                ],
                            ],
                            [
                                message1.id,
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
                                message4.id,
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
                    // link from "testing" to a specific message is new
                    [
                        "testing",
                        new Map([
                            [
                                message7.id,
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
                ]),
            ],
            [
                sales.stream_id,
                new Map([
                    [
                        "new client",
                        new Map([
                            [
                                message5.id,
                                [
                                    {
                                        stream_id: design.stream_id,
                                        topic: "goodbye",
                                        message_id: undefined,
                                    },
                                    // Link to stream with no topic is new
                                    {
                                        stream_id: design.stream_id,
                                        topic: undefined,
                                        message_id: undefined,
                                    },
                                    // Link to #sales>new-client is new
                                    {
                                        stream_id: sales.stream_id,
                                        topic: "new client",
                                        message_id: undefined,
                                    },
                                ],
                            ],
                            // Link from message6 is new
                            [
                                message6.id,
                                [
                                    {
                                        stream_id: sales.stream_id,
                                        topic: "new client",
                                        message_id: message5.id,
                                    },
                                ],
                            ],
                        ]),
                    ],
                ]),
            ],
        ]),
    );

    // ------ Now let's test `topic_links_from_narrow` and `topic_links_to_narrow`

    // Test empty cases.
    assert.deepEqual(
        message_store.topic_links_from_narrow(development.stream_id, "nothing here"),
        [],
    );
    assert.deepEqual(
        message_store.topic_links_to_narrow(development.stream_id, "nothing here"),
        [],
    );

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

    // Links from #sales>new-client to #sales>new-client don't show up in either list
    assert.deepEqual(message_store.topic_links_from_narrow(sales.stream_id, "new client"), [
        {
            text: "#design > goodbye",
            url: "#narrow/channel/10-design/topic/goodbye",
        },
        {
            text: "#design",
            url: "#narrow/channel/10-design",
        },
    ]);
    assert.deepEqual(message_store.topic_links_to_narrow(sales.stream_id, "new client"), []);

    // ------ Now let's test editing a message's topic
    message_store.process_topic_edit({
        message_ids: [message1.id],
        // previously #development
        new_stream_id: sales.stream_id,
        // previously "engineering"
        new_topic: "super engineering",
    });
    // Mirroring how message_events.ts updates the message object after.
    message1.stream_id = sales.stream_id;
    message1.topic = "super engineering";
    assert.deepEqual(message_store.topic_links_to_narrow(design.stream_id, "goodbye"), [
        {
            text: "#sales > new client @ 💬",
            url: "#narrow/channel/12-sales/topic/new.20client/near/3",
        },
        // This existing link is updated to the new stream and topic for message 201
        {
            text: "#sales > super engineering @ 💬",
            url: "#narrow/channel/12-sales/topic/super.20engineering/near/201",
        },
        {
            text: "#development > testing @ 💬",
            url: "#narrow/channel/11-development/topic/testing/near/400",
        },
    ]);

    // This message has the link to the message with id 400 in #development>testing
    // and we'll move it to a new stream/topic.
    message_store.process_topic_edit({
        message_ids: [message2.id],
        // previously #design
        new_stream_id: sales.stream_id,
        // previously "goodbye"
        new_topic: "signing off",
    });
    // Mirroring how message_events.ts updates the message object after.
    message2.stream_id = sales.stream_id;
    message2.topic = "signing off";
    assert.deepEqual(
        message_store.topic_links_to_narrow(design.stream_id, "goodbye"),
        // Links to the original narrow aren't affected
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
            // This link from the moved message now links from the new topic
            text: "#development > testing @ 💬",
            url: "#narrow/channel/11-development/topic/testing/near/400",
        },
    ]);

    // Moving message5, which has both these links in it (which you can see above in the map)
    assert.deepEqual(message_store.topic_links_from_narrow(sales.stream_id, "new client"), [
        {
            text: "#design > goodbye",
            url: "#narrow/channel/10-design/topic/goodbye",
        },
        {
            text: "#design",
            url: "#narrow/channel/10-design",
        },
    ]);
    message_store.process_topic_edit({
        message_ids: [message5.id],
        // previously #sales
        new_stream_id: design.stream_id,
        // previously "new client"
        new_topic: "client logo",
    });
    // Mirroring how message_events.ts updates the message object after.
    message5.stream_id = design.stream_id;
    message5.topic = "client logo";
    // Nothing from #sales>new-client anymore, since they both were from message5.
    assert.deepEqual(message_store.topic_links_from_narrow(sales.stream_id, "new client"), []);
    // Now they're both in the new stream/topic links, but we get an extra link too!
    assert.deepEqual(message_store.topic_links_from_narrow(design.stream_id, "client logo"), [
        {
            text: "#design > goodbye",
            url: "#narrow/channel/10-design/topic/goodbye",
        },
        {
            text: "#design",
            url: "#narrow/channel/10-design",
        },
        // This was an existing link to the old topic from message5. It still links to the
        // old topic (the topic still exists, separately from the message that was moved)
        // and previously wasn't showing up because it was a link from a topic to itself.
        // Now it does show up here because it's a link to a topic different from itself,
        // now that the message is moved.
        {
            text: "#sales > new client",
            url: "#narrow/channel/12-sales/topic/new.20client",
        },
    ]);

    // ------ Now let's test editing a message's id
    // We already have a link to this message, but let's also make links from this message,
    // to test both update correctly. One to a specific message and one to a channel.
    save_message_link(
        sales.stream_id,
        "signing off",
        message2.id,
        "/#narrow/channel/10-design/topic/goodbye/",
    );
    save_message_link(sales.stream_id, "signing off", message2.id, "/#narrow/channel/10-design/");
    assert.deepEqual(message_store.topic_links_from_narrow(development.stream_id, "testing"), [
        {
            text: "#sales > signing off @ 💬",
            url: "#narrow/channel/12-sales/topic/signing.20off/near/5",
        },
    ]);
    assert.deepEqual(message_store.topic_links_from_narrow(sales.stream_id, "signing off"), [
        {
            text: "#design > goodbye",
            url: "#narrow/channel/10-design/topic/goodbye",
        },
        {
            text: "#design",
            url: "#narrow/channel/10-design",
        },
    ]);
    message_store.reify_message_id({old_id: message2.id, new_id: 55});
    assert.deepEqual(message_store.topic_links_from_narrow(development.stream_id, "testing"), [
        {
            text: "#sales > signing off @ 💬",
            url: "#narrow/channel/12-sales/topic/signing.20off/near/55",
        },
    ]);
    // This looks the same but is now stored under a message by a different id,
    // which will let us delete it shortly.
    assert.deepEqual(message_store.topic_links_from_narrow(sales.stream_id, "signing off"), [
        {
            text: "#design > goodbye",
            url: "#narrow/channel/10-design/topic/goodbye",
        },
        {
            text: "#design",
            url: "#narrow/channel/10-design",
        },
    ]);

    // ------ Now let's test removing a message
    message_store.remove([55]);
    assert.deepEqual(message_store.topic_links_from_narrow(development.stream_id, "testing"), []);
    assert.deepEqual(message_store.topic_links_from_narrow(sales.stream_id, "signing off"), []);
});
