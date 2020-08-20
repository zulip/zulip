"use strict";

zrequire("Filter", "js/filter");
const people = zrequire("people");
zrequire("stream_data");
zrequire("unread");

set_global("message_store", {});
set_global("page_params", {});

set_global("muting", {
    is_topic_muted: () => false,
});

// The main code we are testing lives here.
zrequire("narrow_state");

const alice = {
    email: "alice@example.com",
    user_id: 11,
    full_name: "Alice",
};

people.init();
people.add_active_user(alice);
people.is_my_user_id = () => false;

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
    let unread_ids;
    let terms;

    const sub = {
        name: "My Stream",
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
    message_store.get = (msg_id) => {
        assert.equal(msg_id, stream_msg.id);
        return stream_msg;
    };

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

    terms = [{operator: "sender", operand: "me@example.com"}];
    set_filter(terms);
    // note that our candidate ids are just "all" ids now
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id]);

    // this actually does filtering
    assert_unread_info({flavor: "not_found"});

    terms = [{operator: "pm-with", operand: "alice@example.com"}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    unread.process_loaded_messages([private_msg]);

    message_store.get = (msg_id) => {
        assert.equal(msg_id, private_msg.id);
        return private_msg;
    };

    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [private_msg.id]);

    assert_unread_info({
        flavor: "found",
        msg_id: private_msg.id,
    });

    terms = [{operator: "is", operand: "private"}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [private_msg.id]);

    // For a negated search, our candidate ids will be all
    // unread messages, even ones that don't pass the filter.
    terms = [{operator: "is", operand: "private", negated: true}];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id, private_msg.id]);

    terms = [{operator: "pm-with", operand: "bob@example.com"}];
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

run_test("defensive code", () => {
    // Test defensive code.  We actually avoid calling
    // _possible_unread_message_ids for any case where we
    // couldn't compute the unread message ids, but that
    // invariant is hard to future-proof.
    narrow_state._possible_unread_message_ids = () => undefined;
    const terms = [{operator: "some-unhandled-case", operand: "whatever"}];
    set_filter(terms);
    assert_unread_info({
        flavor: "cannot_compute",
    });
});
