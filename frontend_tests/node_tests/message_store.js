"use strict";

const util = zrequire("util");
zrequire("pm_conversations");
const people = zrequire("people");
zrequire("message_store");

const noop = function () {};

set_global("$", global.make_zjquery());
set_global("document", "document-stub");

set_global("alert_words", {
    process_message: noop,
});

set_global("stream_topic_history", {
    add_message: noop,
});

set_global("recent_senders", {
    process_message_for_senders: noop,
});

set_global("page_params", {
    realm_allow_message_editing: true,
    is_admin: true,
});

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

run_test("add_message_metadata", () => {
    let message = {
        sender_email: "me@example.com",
        sender_id: me.user_id,
        type: "private",
        display_recipient: convert_recipients([me, bob, cindy]),
        flags: ["has_alert_word"],
        is_me_message: false,
        id: 2067,
    };
    message_store.set_message_booleans(message);
    message_store.add_message_metadata(message);

    assert.deepEqual(message_store.user_ids().sort(), [me.user_id, bob.user_id, cindy.user_id]);

    assert.equal(message.is_private, true);
    assert.equal(message.reply_to, "bob@example.com,cindy@example.com");
    assert.equal(message.to_user_ids, "103,104");
    assert.equal(message.display_reply_to, "Bob, Cindy");
    assert.equal(message.alerted, true);
    assert.equal(message.is_me_message, false);

    let retrieved_message = message_store.get(2067);
    assert.equal(retrieved_message, message);

    blueslip.expect("error", "message_store got non-number: 2067");
    retrieved_message = message_store.get("2067");
    assert.equal(retrieved_message, message);

    // access cached previous message, and test match subject/content
    message = {
        id: 2067,
        match_subject: "topic foo",
        match_content: "bar content",
    };
    message = message_store.add_message_metadata(message);

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
    };

    message_store.set_message_booleans(message);
    message_store.add_message_metadata(message);
    assert.deepEqual(message.stream, message.display_recipient);
    assert.equal(message.reply_to, "denise@example.com");
    assert.deepEqual(message.flags, undefined);
    assert.equal(message.alerted, false);

    assert.deepEqual(message_store.user_ids().sort(), [
        me.user_id,
        bob.user_id,
        cindy.user_id,
        denise.user_id,
    ]);
});

run_test("message_booleans_parity", () => {
    // We have two code paths that update/set message booleans.
    // This test asserts that both have identical behavior for the
    // flags common between them.
    const assert_bool_match = (flags, expected_message) => {
        const set_message = {topic: "set_message_booleans", flags};
        const update_message = {topic: "update_booleans"};
        message_store.set_message_booleans(set_message);
        message_store.update_booleans(update_message, flags);
        Object.keys(expected_message).forEach((key) => {
            assert.equal(
                set_message[key],
                expected_message[key],
                `'${key}' != ${expected_message[key]}`,
            );
            assert.equal(update_message[key], expected_message[key]);
        });
        assert.equal(set_message.topic, "set_message_booleans");
        assert.equal(update_message.topic, "update_booleans");
    };

    assert_bool_match(["wildcard_mentioned"], {
        mentioned: true,
        mentioned_me_directly: false,
        alerted: false,
    });

    assert_bool_match(["mentioned"], {
        mentioned: true,
        mentioned_me_directly: true,
        alerted: false,
    });

    assert_bool_match(["has_alert_word"], {
        mentioned: false,
        mentioned_me_directly: false,
        alerted: true,
    });
});

run_test("errors", () => {
    // Test a user that doesn't exist
    let message = {
        type: "private",
        display_recipient: [{id: 92714}],
    };

    blueslip.expect("error", "Unknown user_id in get_by_user_id: 92714", 2);
    blueslip.expect("error", "Unknown user id 92714", 2); // From person.js

    // Expect each to throw two blueslip errors
    // One from message_store.js, one from person.js
    const emails = message_store.get_pm_emails(message);
    assert.equal(emails, "?");

    const names = message_store.get_pm_full_names(message);
    assert.equal(names, "?");

    message = {
        type: "stream",
        display_recipient: [{}],
    };

    // This should early return and not run pm_conversation.set_partner
    let num_partner = 0;
    set_global("pm_conversation", {
        set_partner() {
            num_partner += 1;
        },
    });
    message_store.process_message_for_recent_private_messages(message);
    assert.equal(num_partner, 0);
});

run_test("update_booleans", () => {
    const message = {};

    // First, test fields that we do actually want to update.
    message.mentioned = false;
    message.mentioned_me_directly = false;
    message.alerted = false;

    let flags = ["mentioned", "has_alert_word", "read"];
    message_store.update_booleans(message, flags);
    assert.equal(message.mentioned, true);
    assert.equal(message.mentioned_me_directly, true);
    assert.equal(message.alerted, true);

    flags = ["wildcard_mentioned", "unread"];
    message_store.update_booleans(message, flags);
    assert.equal(message.mentioned, true);
    assert.equal(message.mentioned_me_directly, false);

    flags = ["read"];
    message_store.update_booleans(message, flags);
    assert.equal(message.mentioned, false);
    assert.equal(message.mentioned_me_directly, false);
    assert.equal(message.alerted, false);

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

run_test("update_property", () => {
    const message1 = {
        type: "stream",
        sender_full_name: alice.full_name,
        sender_id: alice.user_id,
        small_avatar_url: "alice_url",
        stream_id: devel.stream_id,
        stream: devel.name,
        display_recipient: devel.name,
        id: 100,
    };
    const message2 = {
        type: "stream",
        sender_full_name: bob.full_name,
        sender_id: bob.user_id,
        small_avatar_url: "bob_url",
        stream_id: denmark.stream_id,
        stream: denmark.name,
        display_recipient: denmark.name,
        id: 101,
    };
    for (const message of [message1, message2]) {
        message_store.set_message_booleans(message);
        message_store.add_message_metadata(message);
    }

    assert.equal(message1.sender_full_name, alice.full_name);
    assert.equal(message2.sender_full_name, bob.full_name);
    message_store.update_property("sender_full_name", "Bobby", {user_id: bob.user_id});
    assert.equal(message1.sender_full_name, alice.full_name);
    assert.equal(message2.sender_full_name, "Bobby");

    assert.equal(message1.small_avatar_url, "alice_url");
    assert.equal(message2.small_avatar_url, "bob_url");
    message_store.update_property("small_avatar_url", "bobby_url", {user_id: bob.user_id});
    assert.equal(message1.small_avatar_url, "alice_url");
    assert.equal(message2.small_avatar_url, "bobby_url");

    assert.equal(message1.stream, devel.name);
    assert.equal(message1.display_recipient, devel.name);
    assert.equal(message2.stream, denmark.name);
    assert.equal(message2.display_recipient, denmark.name);
    message_store.update_property("stream_name", "Prod", {stream_id: devel.stream_id});
    assert.equal(message1.stream, "Prod");
    assert.equal(message1.display_recipient, "Prod");
    assert.equal(message2.stream, denmark.name);
    assert.equal(message2.display_recipient, denmark.name);
});

run_test("each", () => {
    message_store.each((message) => {
        assert(message.alerted !== undefined);
    });
});

run_test("message_id_change", () => {
    const message = {
        sender_email: "me@example.com",
        sender_id: me.user_id,
        type: "private",
        display_recipient: convert_recipients([me, bob, cindy]),
        flags: ["has_alert_word"],
        id: 401,
    };
    message_store.add_message_metadata(message);

    set_global("pointer", {
        furthest_read: 401,
        set_furthest_read(value) {
            this.furthest_read = value;
        },
    });

    set_global("message_list", {});
    set_global("home_msg_list", {});

    const opts = {
        old_id: 401,
        new_id: 402,
    };

    global.with_stub((stub) => {
        home_msg_list.change_message_id = stub.f;
        message_store.reify_message_id(opts);
        const msg_id = stub.get_args("old", "new");
        assert.equal(msg_id.old, 401);
        assert.equal(msg_id.new, 402);
    });

    home_msg_list.view = {};
    global.with_stub((stub) => {
        home_msg_list.view.change_message_id = stub.f;
        message_store.reify_message_id(opts);
        const msg_id = stub.get_args("old", "new");
        assert.equal(msg_id.old, 401);
        assert.equal(msg_id.new, 402);
    });
});

run_test("errors", () => {
    blueslip.expect("error", "message_store.get got bad value: undefined");
    message_store.get(undefined);
});
