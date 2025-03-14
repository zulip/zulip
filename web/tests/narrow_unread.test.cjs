"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

mock_esm("../src/user_topics", {
    is_topic_muted: () => false,
});

const {Filter} = zrequire("../src/filter");
const message_store = zrequire("message_store");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const unread = zrequire("unread");
// The main code we are testing lives here.
const narrow_state = zrequire("narrow_state");
const message_lists = zrequire("message_lists");
const {set_current_user, set_realm} = zrequire("state_data");

set_current_user({});
set_realm({});

const alice = {
    email: "alice@example.com",
    user_id: 11,
    full_name: "Alice",
};

const bogus_stream_id = "999999";

people.init();
people.add_active_user(alice);

function set_filter(terms) {
    const filter = new Filter(terms);
    filter.try_adjusting_for_moved_with_target();
    message_lists.set_current({
        data: {
            filter,
        },
    });
}

function assert_unread_info(expected) {
    assert.deepEqual(
        narrow_state.get_first_unread_info(message_lists.current?.data.filter),
        expected,
    );
}

function candidate_ids() {
    return narrow_state._possible_unread_message_ids(message_lists.current?.data.filter);
}

run_test("get_unread_ids", () => {
    unread.declare_bankruptcy();
    message_lists.set_current(undefined);

    let unread_ids;
    let terms;

    const sub = {
        name: "My stream",
        stream_id: 55,
    };

    const stream_msg = {
        id: 101,
        type: "stream",
        stream_id: sub.stream_id,
        display_recipient: sub.name,
        topic: "my topic",
        unread: true,
        mentioned: true,
        mentioned_me_directly: true,
    };

    const private_msg = {
        id: 102,
        type: "private",
        unread: true,
        display_recipient: [{id: alice.user_id, email: alice.email}],
    };

    const other_topic_message = {
        id: 103,
        type: "stream",
        stream_id: sub.stream_id,
        display_recipient: sub.name,
        topic: "another topic",
        unread: true,
        mentioned: false,
        mentioned_me_directly: false,
    };

    message_store.update_message_cache(stream_msg);
    message_store.update_message_cache(private_msg);
    message_store.update_message_cache(other_topic_message);

    stream_data.add_sub(sub);

    terms = [{operator: "search", operand: "whatever"}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.equal(unread_ids, undefined);
    assert_unread_info({flavor: "cannot_compute"});

    terms = [{operator: "bogus_operator", operand: "me@example.com"}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);
    assert_unread_info({flavor: "not_found"});

    terms = [{operator: "stream", operand: bogus_stream_id}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    terms = [{operator: "stream", operand: sub.stream_id.toString()}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);
    assert_unread_info({flavor: "not_found"});

    unread.process_loaded_messages([stream_msg]);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id]);
    assert_unread_info({
        flavor: "found",
        msg_id: stream_msg.id,
    });

    terms = [
        {operator: "stream", operand: bogus_stream_id},
        {operator: "topic", operand: "my topic"},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    terms = [
        {operator: "stream", operand: sub.stream_id.toString()},
        {operator: "topic", operand: "my topic"},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id]);

    terms = [{operator: "is", operand: "mentioned"}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id]);

    terms = [{operator: "is", operand: "resolved"}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id]);

    terms = [{operator: "sender", operand: "me@example.com"}];
    set_filter(terms);
    // note that our candidate ids are just "all" ids now
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id]);

    // this actually does filtering
    assert_unread_info({flavor: "not_found"});

    terms = [{operator: "dm", operand: "alice@example.com"}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    unread.process_loaded_messages([private_msg]);

    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [private_msg.id]);

    assert_unread_info({
        flavor: "found",
        msg_id: private_msg.id,
    });

    // "is:private" was renamed to "is:dm"
    terms = [{operator: "is", operand: "private"}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [private_msg.id]);

    terms = [{operator: "is", operand: "dm"}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [private_msg.id]);

    // For a negated search, our candidate ids will be all
    // unread messages, even ones that don't pass the filter.
    terms = [{operator: "is", operand: "dm", negated: true}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id, private_msg.id]);

    terms = [{operator: "dm", operand: "bob@example.com"}];
    set_filter(terms);

    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    terms = [{operator: "is", operand: "starred"}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    terms = [{operator: "search", operand: "needle"}];
    set_filter(terms);

    assert_unread_info({
        flavor: "cannot_compute",
    });

    // For a search using `with` operator, our candidate ids
    // will be the messages present in the channel/topic
    // containing the message for which the `with` operand
    // is id to.
    //
    // Here we use an empty topic for the operators, and show that
    // adding the with operator causes us to see unreads in the
    // destination topic.
    unread.process_loaded_messages([other_topic_message]);
    terms = [
        {operator: "channel", operand: sub.stream_id.toString()},
        {operator: "topic", operand: "another topic"},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [other_topic_message.id]);

    terms = [
        {operator: "channel", operand: sub.stream_id.toString()},
        {operator: "topic", operand: "another topic"},
        {operator: "with", operand: stream_msg.id},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id]);

    terms = [
        {operator: "channel", operand: sub.stream_id.toString()},
        {operator: "topic", operand: "another topic"},
        {operator: "with", operand: private_msg.id},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [private_msg.id]);
});

run_test("defensive code", ({override_rewire}) => {
    // Test defensive code.  We actually avoid calling
    // _possible_unread_message_ids for any case where we
    // couldn't compute the unread message ids, but that
    // invariant is hard to future-proof.
    override_rewire(narrow_state, "_possible_unread_message_ids", () => undefined);
    const terms = [{operator: "some-unhandled-case", operand: "whatever"}];
    set_filter(terms);
    assert_unread_info({
        flavor: "cannot_compute",
    });
});
