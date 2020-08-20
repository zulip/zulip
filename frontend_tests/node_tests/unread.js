"use strict";

const _ = require("lodash");

zrequire("muting");
const people = zrequire("people");
zrequire("stream_data");
zrequire("unread");

set_global("page_params", {
    realm_push_notifications_enabled: false,
});
zrequire("settings_notifications");

const FoldDict = zrequire("fold_dict").FoldDict;

set_global("narrow_state", {});
set_global("current_msg_list", {});
set_global("home_msg_list", {});
set_global("message_store", {});

const me = {
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
};
people.add_active_user(me);
people.initialize_current_user(me.user_id);

const social = {
    stream_id: 200,
    name: "social",
    subscribed: true,
    is_muted: false,
};
stream_data.add_sub(social);

function assert_zero_counts(counts) {
    assert.equal(counts.private_message_count, 0);
    assert.equal(counts.home_unread_messages, 0);
    assert.equal(counts.mentioned_message_count, 0);
    assert.equal(counts.stream_count.size, 0);
    assert.equal(counts.pm_count.size, 0);
}

function test_notifiable_count(home_unread_messages, expected_notifiable_count) {
    set_global("page_params", {
        desktop_icon_count_display: 1,
    });
    let notifiable_counts = unread.get_notifiable_count();
    assert.deepEqual(notifiable_counts, home_unread_messages);
    set_global("page_params", {
        desktop_icon_count_display: 2,
    });
    notifiable_counts = unread.get_notifiable_count();
    assert.deepEqual(notifiable_counts, expected_notifiable_count);
    set_global("page_params", {
        desktop_icon_count_display: 3,
    });
    notifiable_counts = unread.get_notifiable_count();
    assert.deepEqual(notifiable_counts, 0);
}

run_test("empty_counts_while_narrowed", () => {
    const counts = unread.get_counts();
    assert_zero_counts(counts);
    test_notifiable_count(counts.home_unread_messages, 0);
});

run_test("empty_counts_while_home", () => {
    const counts = unread.get_counts();
    assert_zero_counts(counts);
    test_notifiable_count(counts.home_unread_messages, 0);
});

run_test("changing_topics", () => {
    // Summary: change the topic of a message from 'lunch'
    // to 'dinner' using update_unread_topics().
    let count = unread.num_unread_for_topic(social.stream_id, "lunch");
    assert.equal(count, 0);

    const stream_id = 100;
    const wrong_stream_id = 110;

    const message = {
        id: 15,
        type: "stream",
        stream_id,
        topic: "luNch",
        unread: true,
    };

    const other_message = {
        id: 16,
        type: "stream",
        stream_id,
        topic: "lunCH",
        unread: true,
    };

    assert.deepEqual(unread.get_unread_message_ids([15, 16]), []);
    assert.deepEqual(unread.get_unread_messages([message, other_message]), []);

    let msg_ids = unread.get_msg_ids_for_topic(stream_id, "LuNcH");
    assert.deepEqual(msg_ids, []);

    msg_ids = unread.get_msg_ids_for_stream(stream_id);
    assert.deepEqual(msg_ids, []);

    unread.process_loaded_messages([message, other_message]);

    assert.deepEqual(unread.get_all_msg_ids(), [15, 16]);
    assert.deepEqual(unread.get_unread_message_ids([15, 16]), [15, 16]);
    assert.deepEqual(unread.get_unread_messages([message, other_message]), [
        message,
        other_message,
    ]);

    count = unread.num_unread_for_topic(stream_id, "Lunch");
    assert.equal(count, 2);
    assert(unread.topic_has_any_unread(stream_id, "lunch"));
    assert(!unread.topic_has_any_unread(wrong_stream_id, "lunch"));
    assert(!unread.topic_has_any_unread(stream_id, "NOT lunch"));

    count = unread.num_unread_for_topic(stream_id, "NOT lunch");
    assert.equal(count, 0);

    msg_ids = unread.get_msg_ids_for_topic(stream_id, "NOT lunch");
    assert.deepEqual(msg_ids, []);

    let event = {
        topic: "dinner",
    };

    unread.update_unread_topics(message, event);

    count = unread.num_unread_for_topic(stream_id, "lUnch");
    assert.equal(count, 1);

    count = unread.num_unread_for_topic(stream_id, "dinner");
    assert.equal(count, 1);

    event = {
        topic: "snack",
    };

    unread.update_unread_topics(other_message, event);

    count = unread.num_unread_for_topic(stream_id, "lunch");
    assert.equal(count, 0);
    assert(!unread.topic_has_any_unread(stream_id, "lunch"));
    assert(!unread.topic_has_any_unread(wrong_stream_id, "lunch"));

    count = unread.num_unread_for_topic(stream_id, "snack");
    assert.equal(count, 1);
    assert(unread.topic_has_any_unread(stream_id, "snack"));
    assert(!unread.topic_has_any_unread(wrong_stream_id, "snack"));

    // Test defensive code.  Trying to update a message we don't know
    // about should be a no-op.
    event = {
        topic: "brunch",
    };
    unread.update_unread_topics(other_message, event);

    // Update a message that was never marked as unread.
    const sticky_message = {
        id: 17,
        type: "stream",
        stream_id,
        topic: "sticky",
        unread: true,
    };

    const message_dict = new Map();
    message_dict.set(message.id, message);
    message_dict.set(other_message.id, other_message);
    message_dict.set(sticky_message.id, sticky_message);

    message_store.get = function (msg_id) {
        return message_dict.get(msg_id);
    };

    unread.process_loaded_messages([sticky_message]);
    count = unread.num_unread_for_topic(stream_id, "sticky");
    assert.equal(count, 1);
    assert(sticky_message.unread);

    unread.mark_as_read(sticky_message.id);
    count = unread.num_unread_for_topic(stream_id, "sticky");
    assert.equal(count, 0);
    assert(!sticky_message.unread);

    event = {
        topic: "sticky",
    };

    unread.update_unread_topics(sticky_message, event);
    count = unread.num_unread_for_topic(stream_id, "sticky");
    assert.equal(count, 0);

    // cleanup
    unread.mark_as_read(message.id);
    count = unread.num_unread_for_topic(stream_id, "dinner");
    assert.equal(count, 0);

    unread.mark_as_read(other_message.id);
    count = unread.num_unread_for_topic(stream_id, "snack");
    assert.equal(count, 0);

    // test coverage
    unread.update_unread_topics(sticky_message, {});
});

run_test("muting", () => {
    unread.declare_bankruptcy();

    const stream_id = social.stream_id;
    const unknown_stream_id = 555;

    const message = {
        id: 15,
        type: "stream",
        stream_id,
        topic: "test_muting",
        unread: true,
    };

    unread.process_loaded_messages([message]);
    let counts = unread.get_counts();
    assert.equal(counts.stream_count.get(stream_id), 1);
    assert.equal(counts.home_unread_messages, 1);
    assert.equal(unread.num_unread_for_stream(stream_id), 1);
    assert.deepEqual(unread.get_msg_ids_for_stream(stream_id), [message.id]);
    test_notifiable_count(counts.home_unread_messages, 0);

    muting.add_muted_topic(social.stream_id, "test_muting");
    counts = unread.get_counts();
    assert.equal(counts.stream_count.get(stream_id), 0);
    assert.equal(counts.home_unread_messages, 0);
    assert.equal(unread.num_unread_for_stream(stream_id), 0);
    assert.deepEqual(unread.get_msg_ids_for_stream(stream_id), []);
    test_notifiable_count(counts.home_unread_messages, 0);

    // we still find the message id here (muting is ignored)
    assert.deepEqual(unread.get_all_msg_ids(), [message.id]);

    assert.equal(unread.num_unread_for_stream(unknown_stream_id), 0);
});

run_test("num_unread_for_topic", () => {
    // Test the num_unread_for_topic() function using many
    // messages.
    unread.declare_bankruptcy();

    const stream_id = 301;

    stream_data.get_sub_by_id = function (arg) {
        if (arg === stream_id) {
            return {name: "Some Stream"};
        }
    };

    let count = unread.num_unread_for_topic(stream_id, "lunch");
    assert.equal(count, 0);

    const message = {
        type: "stream",
        stream_id,
        topic: "LuncH",
        unread: true,
    };

    // Put messages into list in reverse order to try to confuse
    // our sort.
    const num_msgs = 500;
    let i;
    for (i = num_msgs; i > 0; i -= 1) {
        message.id = i;
        unread.process_loaded_messages([message]);
    }

    count = unread.num_unread_for_topic(stream_id, "lunch");
    assert.equal(count, num_msgs);

    let msg_ids = unread.get_msg_ids_for_topic(stream_id, "LuNcH");
    assert.deepEqual(msg_ids, _.range(1, 501));

    msg_ids = unread.get_msg_ids_for_stream(stream_id);
    assert.deepEqual(msg_ids, _.range(1, 501));

    const topic_dict = new FoldDict();

    let missing_topics = unread.get_missing_topics({
        stream_id,
        topic_dict,
    });

    assert.deepEqual(missing_topics, [{pretty_name: "LuncH", message_id: 500}]);

    topic_dict.set("lUNCh", "whatever");

    missing_topics = unread.get_missing_topics({
        stream_id,
        topic_dict,
    });

    assert.deepEqual(missing_topics, []);

    for (i = 0; i < num_msgs; i += 1) {
        message.id = i + 1;
        unread.mark_as_read(message.id);
    }

    count = unread.num_unread_for_topic(stream_id, "lunch");
    assert.equal(count, 0);

    msg_ids = unread.get_msg_ids_for_topic(stream_id, "LuNcH");
    assert.deepEqual(msg_ids, []);

    msg_ids = unread.get_msg_ids_for_stream(stream_id);
    assert.deepEqual(msg_ids, []);
});

run_test("home_messages", () => {
    stream_data.is_subscribed = function () {
        return true;
    };
    stream_data.is_muted = function () {
        return false;
    };

    const stream_id = 401;

    stream_data.get_sub_by_id = function () {
        return {
            name: "whatever",
        };
    };

    const message = {
        id: 15,
        type: "stream",
        stream_id,
        topic: "lunch",
        unread: true,
    };

    let counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);
    test_notifiable_count(counts.home_unread_messages, 0);

    unread.process_loaded_messages([message]);

    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 1);
    assert.equal(counts.stream_count.get(stream_id), 1);
    test_notifiable_count(counts.home_unread_messages, 0);
    unread.mark_as_read(message.id);
    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);
    test_notifiable_count(counts.home_unread_messages, 0);

    unread.process_loaded_messages([message]);
    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 1);
    test_notifiable_count(counts.home_unread_messages, 0);

    // Now unsubscribe all our streams.
    stream_data.is_subscribed = function () {
        return false;
    };
    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);
    test_notifiable_count(counts.home_unread_messages, 0);
});

run_test("phantom_messages", () => {
    const message = {
        id: 999,
        type: "stream",
        stream_id: 555,
        topic: "phantom",
    };

    stream_data.get_sub_by_id = function () {
        return;
    };

    unread.mark_as_read(message.id);
    const counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);
    test_notifiable_count(counts.home_unread_messages, 0);
});

run_test("private_messages", () => {
    let counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);

    const anybody = {
        email: "anybody@example.com",
        user_id: 999,
        full_name: "Any Body",
    };
    people.add_active_user(anybody);

    const message = {
        id: 15,
        type: "private",
        display_recipient: [{id: anybody.user_id}, {id: me.user_id}],
        unread: true,
    };

    unread.process_loaded_messages([message]);

    counts = unread.get_counts();
    assert.equal(counts.private_message_count, 1);
    assert.equal(counts.pm_count.get("999"), 1);
    test_notifiable_count(counts.home_unread_messages, 1);
    unread.mark_as_read(message.id);
    counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);
    assert.equal(counts.pm_count.get("999"), 0);
    test_notifiable_count(counts.home_unread_messages, 0);
});

run_test("private_messages", () => {
    const alice = {
        email: "alice@example.com",
        user_id: 101,
        full_name: "Alice",
    };
    people.add_active_user(alice);

    const bob = {
        email: "bob@example.com",
        user_id: 102,
        full_name: "Bob",
    };
    people.add_active_user(bob);

    assert.equal(unread.num_unread_for_person(alice.user_id.toString()), 0);
    assert.equal(unread.num_unread_for_person(bob.user_id.toString()), 0);
    assert.deepEqual(unread.get_msg_ids_for_person(alice.user_id.toString()), []);
    assert.deepEqual(unread.get_msg_ids_for_person(bob.user_id.toString()), []);
    assert.deepEqual(unread.get_msg_ids_for_person(), []);
    assert.deepEqual(unread.get_msg_ids_for_private(), []);

    const message = {
        id: 15,
        display_recipient: [{id: alice.user_id}],
        type: "private",
        unread: true,
    };

    const read_message = {
        flags: ["read"],
    };
    unread.process_loaded_messages([message, read_message]);
    assert.equal(unread.num_unread_for_person(alice.user_id.toString()), 1);

    assert.equal(unread.num_unread_for_person(""), 0);

    assert.deepEqual(unread.get_msg_ids_for_person(alice.user_id.toString()), [message.id]);
    assert.deepEqual(unread.get_msg_ids_for_person(bob.user_id.toString()), []);
    assert.deepEqual(unread.get_msg_ids_for_private(), [message.id]);
    assert.deepEqual(unread.get_all_msg_ids(), [message.id]);

    unread.mark_as_read(message.id);
    assert.equal(unread.num_unread_for_person(alice.user_id.toString()), 0);
    assert.equal(unread.num_unread_for_person(""), 0);
    assert.deepEqual(unread.get_msg_ids_for_person(alice.user_id.toString()), []);
    assert.deepEqual(unread.get_msg_ids_for_person(bob.user_id.toString()), []);
    assert.deepEqual(unread.get_msg_ids_for_private(), []);
    assert.deepEqual(unread.get_all_msg_ids(), []);
    const counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);
    test_notifiable_count(counts.home_unread_messages, 0);
});

run_test("mentions", () => {
    let counts = unread.get_counts();
    assert.equal(counts.mentioned_message_count, 0);
    assert.deepEqual(unread.get_msg_ids_for_mentions(), []);
    test_notifiable_count(counts.home_unread_messages, 0);

    const muted_stream_id = 401;

    muting.add_muted_topic(401, "lunch");

    const already_read_message = {
        id: 14,
        type: "stream",
        stream_id: 400,
        topic: "lunch",
        mentioned: true,
        mentioned_me_directly: true,
        unread: false,
    };

    const mention_me_message = {
        id: 15,
        type: "stream",
        stream_id: 400,
        topic: "lunch",
        mentioned: true,
        mentioned_me_directly: true,
        unread: true,
    };

    const mention_all_message = {
        id: 16,
        type: "stream",
        stream_id: 400,
        topic: "lunch",
        mentioned: true,
        mentioned_me_directly: false,
        unread: true,
    };

    // This message shouldn't affect the unread mention counts.
    const muted_mention_all_message = {
        id: 17,
        type: "stream",
        stream_id: muted_stream_id,
        topic: "lunch",
        mentioned: true,
        mentioned_me_directly: false,
        unread: true,
    };

    unread.process_loaded_messages([
        already_read_message,
        mention_me_message,
        mention_all_message,
        muted_mention_all_message,
    ]);

    counts = unread.get_counts();
    assert.equal(counts.mentioned_message_count, 2);
    assert.deepEqual(unread.get_msg_ids_for_mentions(), [
        mention_me_message.id,
        mention_all_message.id,
    ]);
    assert.deepEqual(unread.get_all_msg_ids(), [
        mention_me_message.id,
        mention_all_message.id,
        muted_mention_all_message.id,
    ]);
    test_notifiable_count(counts.home_unread_messages, 2);

    unread.mark_as_read(mention_me_message.id);
    unread.mark_as_read(mention_all_message.id);
    counts = unread.get_counts();
    assert.equal(counts.mentioned_message_count, 0);
    test_notifiable_count(counts.home_unread_messages, 0);
});

run_test("mention updates", () => {
    const message = {
        id: 17,
        unread: false,
        type: "stream",
    };

    function test_counted(counted) {
        unread.update_message_for_mention(message);
        assert.equal(unread.unread_mentions_counter.has(message.id), counted);
    }

    test_counted(false);

    message.unread = true;
    message.mentioned = true;
    test_counted(true);

    message.mentioned = false;
    test_counted(false);

    message.mentioned = true;
    test_counted(true);

    message.unread = false;
    test_counted(false);

    message.unread = true;
    test_counted(true);
});

run_test("starring", () => {
    // We don't need any setup here, because we just hard code
    // this to [] in the code.
    assert.deepEqual(unread.get_msg_ids_for_starred(), []);
});

run_test("declare_bankruptcy", () => {
    const message = {
        id: 16,
        type: "whatever",
        stream_id: 1999,
        topic: "whatever",
        mentioned: true,
    };

    unread.process_loaded_messages([message]);

    unread.declare_bankruptcy();

    const counts = unread.get_counts();
    assert_zero_counts(counts);
    test_notifiable_count(counts.home_unread_messages, 0);
});

run_test("message_unread", () => {
    // Test some code that might be overly defensive, for line coverage sake.
    assert(!unread.message_unread(undefined));
    assert(unread.message_unread({unread: true}));
    assert(!unread.message_unread({unread: false}));
});

run_test("server_counts", () => {
    // note that user_id 30 is "me"

    page_params.unread_msgs = {
        pms: [
            {
                sender_id: 101,
                unread_message_ids: [31, 32, 60, 61, 62, 63],
            },
        ],
        huddles: [
            {
                user_ids_string: "4,6,30,101",
                unread_message_ids: [34, 50],
            },
        ],
        streams: [
            {
                stream_id: 1,
                topic: "test",
                unread_message_ids: [33, 35, 36],
            },
        ],
        mentions: [31, 34, 40, 41],
    };

    unread.declare_bankruptcy();
    unread.initialize();

    assert.equal(unread.num_unread_for_person("101"), 6);
    assert.equal(unread.num_unread_for_person("4,6,101"), 2);
    assert.equal(unread.num_unread_for_person("30"), 0);

    assert.equal(unread.num_unread_for_topic(0, "bogus"), 0);
    assert.equal(unread.num_unread_for_topic(1, "bogus"), 0);
    assert.equal(unread.num_unread_for_topic(1, "test"), 3);

    assert.equal(unread.unread_mentions_counter.size, 4);

    unread.mark_as_read(40);
    assert.equal(unread.unread_mentions_counter.size, 3);

    unread.mark_as_read(35);
    assert.equal(unread.num_unread_for_topic(1, "test"), 2);

    unread.mark_as_read(34);
    assert.equal(unread.num_unread_for_person("4,6,101"), 1);
});

run_test("empty_cases", () => {
    unread.declare_bankruptcy();

    const stream_id = 999;
    let msg_ids = unread.get_msg_ids_for_topic(stream_id, "LuNcH");
    assert.deepEqual(msg_ids, []);

    msg_ids = unread.get_msg_ids_for_stream(stream_id);
    assert.deepEqual(msg_ids, []);
    assert.deepEqual(unread.get_all_msg_ids(), []);

    const missing_topics = unread.get_missing_topics({
        stream_id,
        topic_dict: "should-never-be-referenced",
    });
    assert.deepEqual(missing_topics, []);
});

run_test("errors", () => {
    unread.declare_bankruptcy();

    // Test unknown message leads to zero count
    const message = {
        id: 9,
        type: "private",
        display_recipient: [{id: 9999}],
    };

    unread.mark_as_read(message.id);
    const counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);
    test_notifiable_count(counts.home_unread_messages, 0);
});
