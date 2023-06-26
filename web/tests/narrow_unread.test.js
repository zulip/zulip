"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");

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

const alice = {
    email: "alice@example.com",
    user_id: 11,
    full_name: "Alice",
};

people.init();
people.add_active_user(alice);

function set_filter(terms) {
    const filter = new Filter(terms);
    narrow_state.set_current_filter(filter);
}

function assert_unread_info(expected) {
    assert.deepEqual(narrow_state.get_first_unread_info(), expected);
}

function candidate_ids() {
    return narrow_state._possible_unread_message_ids();
}

run_test("get_unread_ids", () => {
    unread.declare_bankruptcy();
    narrow_state.reset_current_filter();

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
        topic: "my topic",
        unread: true,
        mentioned: true,
        mentioned_me_directly: true,
    };

    const private_msg = {
        id: 102,
        type: "private",
        unread: true,
        display_recipient: [{id: alice.user_id}],
    };

    message_store.update_message_cache(stream_msg);
    message_store.update_message_cache(private_msg);

    stream_data.add_sub(sub);

    unread_ids = candidate_ids();
    assert.equal(unread_ids, undefined);

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

    terms = [{operator: "stream", operand: "bogus"}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    terms = [{operator: "stream", operand: sub.name}];
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
        {operator: "stream", operand: "bogus"},
        {operator: "topic", operand: "my topic"},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    terms = [
        {operator: "stream", operand: sub.name},
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

    narrow_state.reset_current_filter();
    blueslip.expect("error", "unexpected call to get_first_unread_info");
    assert_unread_info({
        flavor: "cannot_compute",
    });
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
