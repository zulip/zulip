"use strict";

const assert = require("node:assert/strict");

const {make_user} = require("./lib/example_user.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const user_topics = zrequire("user_topics");
const muted_users = zrequire("muted_users");
const people = zrequire("people");
const pmc = zrequire("pm_conversations");
const echo_state = zrequire("echo_state");
const {set_current_user} = zrequire("state_data");

const current_user = {};
set_current_user(current_user);

const alice = make_user({
    email: "alice@example.com",
    user_id: 1,
    full_name: "Alice",
});

const isaac = make_user({
    email: "isaac@example.com",
    user_id: 2,
    full_name: "Isaac",
});

const alex = make_user({
    email: "alex@example.com",
    user_id: 3,
    full_name: "Alex",
});

const me = make_user({
    email: "me@example.com",
    user_id: 15,
    full_name: "Me",
});

people.add_active_user(alice);
people.add_active_user(isaac);
people.add_active_user(alex);
people.add_active_user(me);

const params = {
    recent_private_conversations: [
        {user_ids: [alice.user_id], max_message_id: 100},
        {user_ids: [alex.user_id], max_message_id: 99},
        {user_ids: [alice.user_id, isaac.user_id], max_message_id: 98},
        {user_ids: [alice.user_id, isaac.user_id, alex.user_id], max_message_id: 97},
        {user_ids: [me.user_id], max_message_id: 96}, // self
    ],
};

function test(label, f) {
    run_test(label, ({override}) => {
        pmc.clear_for_testing();
        user_topics.set_user_topics([]);
        muted_users.set_muted_users([]);
        echo_state._patch_waiting_for_ack(new Map());
        people.initialize_current_user(me.user_id);
        f({override});
    });
}

test("partners", () => {
    const user1_id = 1;
    const user2_id = 2;
    const user3_id = 3;

    pmc.set_partner(user1_id);
    assert.deepEqual(pmc.get_partners(), [user1_id]);
    pmc.set_partner(user3_id);

    assert.deepEqual(pmc.get_partners(), [user1_id, user3_id]);
    assert.equal(pmc.is_partner(user1_id), true);
    assert.equal(pmc.is_partner(user2_id), false);
    assert.equal(pmc.is_partner(user3_id), true);
});

test("insert_recent_private_message", () => {
    pmc.recent.initialize(params);

    // Base data
    assert.deepEqual(pmc.recent.get(), [
        {user_ids_string: "1", max_message_id: 100, message_count: 0},
        {user_ids_string: "3", max_message_id: 99, message_count: 0},
        {user_ids_string: "1,2", max_message_id: 98, message_count: 0},
        {user_ids_string: "1,2,3", max_message_id: 97, message_count: 0},
        {user_ids_string: "15", max_message_id: 96, message_count: 0},
    ]);

    // Insert new messages (which should rearrange these entries).
    pmc.recent.insert([1], 1000);
    pmc.recent.insert([1, 2, 3], 999);
    // direct message to oneself
    pmc.recent.insert([], 101);

    // Try to backdate user1's latest message.
    pmc.recent.insert([1], 555);

    assert.deepEqual(pmc.recent.get(), [
        {user_ids_string: "1", max_message_id: 1000, message_count: 0},
        {user_ids_string: "1,2,3", max_message_id: 999, message_count: 0},
        {user_ids_string: "15", max_message_id: 101, message_count: 0},
        {user_ids_string: "3", max_message_id: 99, message_count: 0},
        {user_ids_string: "1,2", max_message_id: 98, message_count: 0},
    ]);
    assert.deepEqual(pmc.recent.get_strings(), ["1", "1,2,3", "15", "3", "1,2"]);
});

test("muted_users", () => {
    pmc.recent.initialize(params);

    // Base data
    assert.deepEqual(pmc.recent.get(), [
        {user_ids_string: "1", max_message_id: 100, message_count: 0},
        {user_ids_string: "3", max_message_id: 99, message_count: 0},
        {user_ids_string: "1,2", max_message_id: 98, message_count: 0},
        {user_ids_string: "1,2,3", max_message_id: 97, message_count: 0},
        {user_ids_string: "15", max_message_id: 96, message_count: 0},
    ]);
    assert.deepEqual(pmc.recent.get_strings(), ["1", "3", "1,2", "1,2,3", "15"]);

    // Mute some users.
    muted_users.add_muted_user(1);
    muted_users.add_muted_user(2);

    // We should now get back only those messages which are either-
    // 1:1 direct messages in which the other user hasn't been muted.
    // Direct message groups where there's at least one non-muted participant.
    assert.deepEqual(pmc.recent.get(), [
        {user_ids_string: "3", max_message_id: 99, message_count: 0},
        {user_ids_string: "1,2,3", max_message_id: 97, message_count: 0},
        {user_ids_string: "15", max_message_id: 96, message_count: 0},
    ]);
    assert.deepEqual(pmc.recent.get_strings(), ["3", "1,2,3", "15"]);
});

test("has_conversation", ({override}) => {
    override(current_user, "user_id", me.user_id);
    pmc.recent.initialize(params);

    // Tests if `has_conversation` returns `true` when there are previous
    // messages in the conversation.
    assert.ok(pmc.recent.has_conversation("1"));
    assert.ok(pmc.recent.has_conversation("15"));
    assert.ok(pmc.recent.has_conversation("1,2"));
    assert.ok(pmc.recent.has_conversation("1,2,15"));
    // Check that we canonicalize to sorted order. This isn't
    // functionality we rely on, but seems worth testing.
    assert.ok(pmc.recent.has_conversation("2,1,15"));

    // Since the current filter does not match the DM view, there may be
    // messages in the conversation which are not fetched yet.
    assert.ok(!pmc.recent.has_conversation("1,3"));
    assert.ok(!pmc.recent.has_conversation("2"));
    assert.ok(!pmc.recent.has_conversation("72"));
});

test("increment_message_count_and_remove", () => {
    pmc.recent.initialize(params);

    // initialize seeds counts at zero; increment_message_count records
    // locally-known delivered messages.
    pmc.recent.increment_message_count([alice.user_id]);
    pmc.recent.increment_message_count([alice.user_id]);
    // The server sends [] for direct messages to oneself.
    pmc.recent.increment_message_count([]);

    assert.ok(pmc.recent.has_conversation("3"));
    pmc.recent.remove("3");
    assert.ok(!pmc.recent.has_conversation("3"));
    assert.deepEqual(pmc.recent.get_strings(), ["1", "1,2", "1,2,3", "15"]);

    // Removing a non-existent conversation is a no-op.
    pmc.recent.remove("999");
    assert.deepEqual(pmc.recent.get_strings(), ["1", "1,2", "1,2,3", "15"]);

    // Incrementing the count for an unknown conversation is a no-op.
    pmc.recent.increment_message_count([72]);
    assert.ok(!pmc.recent.has_conversation("72"));
});

test("maybe_remove", () => {
    pmc.recent.initialize(params);

    const verified_conversations = [];
    pmc.set_update_dm_last_message_id((user_ids_string) => {
        verified_conversations.push(user_ids_string);
    });

    // Record two locally-known messages in Alice's 1:1 conversation.
    pmc.recent.increment_message_count([alice.user_id]);
    pmc.recent.increment_message_count([alice.user_id]);

    // Deleting fewer messages than we know about proves the conversation is
    // still non-empty, so we just decrement and never ask the server.
    pmc.recent.maybe_remove([alice.user_id], 1);
    assert.ok(pmc.recent.has_conversation("1"));
    assert.deepEqual(verified_conversations, []);

    // Deleting the rest leaves us with no locally-known messages, so we
    // optimistically remove the conversation and verify with the server.
    pmc.recent.maybe_remove([alice.user_id], 1);
    assert.ok(!pmc.recent.has_conversation("1"));
    assert.deepEqual(verified_conversations, ["1"]);

    // A self-DM (recipients sent as []) is keyed by our own user id.
    pmc.recent.maybe_remove([], 1);
    assert.ok(!pmc.recent.has_conversation("15"));
    assert.deepEqual(verified_conversations, ["1", "15"]);

    // Deleting from a conversation we don't know about is a no-op.
    pmc.recent.maybe_remove([alice.user_id], 1);
    assert.deepEqual(verified_conversations, ["1", "15"]);
});

test("maybe_remove keeps a conversation with an unacked local echo", () => {
    pmc.recent.initialize(params);

    let server_checks = 0;
    pmc.set_update_dm_last_message_id(() => {
        server_checks += 1;
    });

    // One delivered message in Alice's DM, plus an unsent (e.g. failed)
    // local echo that's still visible in the conversation.
    pmc.recent.increment_message_count([alice.user_id]);
    echo_state.set_message_waiting_for_ack("1.01", {
        type: "private",
        id: 1.01,
        display_recipient: [{id: alice.user_id}, {id: me.user_id}],
    });

    // Deleting the delivered message drops the count to zero, but the
    // pending echo keeps the row in the sidebar without a server check.
    pmc.recent.maybe_remove([alice.user_id], 1);
    assert.ok(pmc.recent.has_conversation("1"));
    assert.equal(server_checks, 0);

    // Once the echo is gone (the send succeeds or is cancelled), deleting
    // again leaves no locally-known messages, so we remove the conversation
    // and verify with the server after all.
    echo_state._patch_waiting_for_ack(new Map());
    pmc.recent.maybe_remove([alice.user_id], 1);
    assert.ok(!pmc.recent.has_conversation("1"));
    assert.equal(server_checks, 1);
});
