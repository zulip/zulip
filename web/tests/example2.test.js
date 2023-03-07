"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

// Hopefully the basic patterns for testing data-oriented modules
// are starting to become apparent.  To reinforce that, we will present
// few more examples that also expose you to some of our core
// data objects.  Also, we start testing some objects that have
// deeper dependencies.

const message_helper = zrequire("message_helper");
const message_store = zrequire("message_store");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const stream_topic_history = zrequire("stream_topic_history");
const unread = zrequire("unread");

// It's typical to set up a little bit of data at the top of a
// test module, but you can also do this within tests. Here we
// will set up things at the top.

const isaac = {
    email: "isaac@example.com",
    user_id: 30,
    full_name: "Isaac Newton",
};

const denmark_stream = {
    color: "blue",
    name: "Denmark",
    stream_id: 101,
    subscribed: false,
};

const messages = {
    isaac_to_denmark_stream: {
        id: 400,
        sender_id: isaac.user_id,
        stream_id: denmark_stream.stream_id,
        type: "stream",
        flags: ["has_alert_word"],
        topic: "copenhagen",
        // note we don't have every field that a "real" message
        // would have, and that can be fine
    },
};

// We aren't going to modify isaac in our tests, so we will
// create him at the top.
people.add_active_user(isaac);

// We are going to test a core module called messages_store.js next.
// This is an example of a deep unit test, where our dependencies
// are easy to test.

run_test("message_store", () => {
    message_store.clear_for_testing();
    stream_data.clear_subscriptions();
    stream_data.add_sub(denmark_stream);

    const in_message = {...messages.isaac_to_denmark_stream};

    assert.equal(in_message.alerted, undefined);

    // Let's add a message into our message_store via
    // message_helper.process_new_message.
    assert.equal(message_store.get(in_message.id), undefined);
    message_helper.process_new_message(in_message);
    const message = message_store.get(in_message.id);
    assert.equal(in_message.alerted, true);
    assert.equal(message, in_message);

    // There are more side effects.
    const topic_names = stream_topic_history.get_recent_topic_names(denmark_stream.stream_id);
    assert.deepEqual(topic_names, ["copenhagen"]);
});

// Tracking unread messages is a very fundamental part of the Zulip
// app, and we use the unread object to track unread messages.

run_test("unread", () => {
    unread.declare_bankruptcy();
    stream_data.clear_subscriptions();
    stream_data.add_sub(denmark_stream);

    const stream_id = denmark_stream.stream_id;
    const topic_name = "copenhagen";

    assert.equal(unread.num_unread_for_topic(stream_id, topic_name), 0);

    const in_message = {...messages.isaac_to_denmark_stream};
    message_store.set_message_booleans(in_message);

    unread.process_loaded_messages([in_message]);
    assert.equal(unread.num_unread_for_topic(stream_id, topic_name), 1);
});
