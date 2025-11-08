"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const user_topics = zrequire("user_topics");
const muted_users = zrequire("muted_users");
const people = zrequire("people");
const pmc = zrequire("pm_conversations");
const {set_current_user} = zrequire("state_data");

const current_user = {};
set_current_user(current_user);

const alice = {
    user_id: 1,
    email: "alice@example.com",
    full_name: "Alice",
};

const isaac = {
    user_id: 2,
    email: "isaac@example.com",
    full_name: "Isaac",
};

const alex = {
    user_id: 3,
    email: "alex@example.com",
    full_name: "Alex",
};

const me = {
    user_id: 15,
    email: "me@example.com",
    full_name: "Me",
};

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
        people.initialize_current_user(me.user_id);
        f({override});
    });
}

test("partners", () => {
    const user1_id = 1;
    const user2_id = 2;
    const user3_id = 3;

    pmc.set_partner(user1_id);
    pmc.set_partner(user3_id);

    assert.equal(pmc.is_partner(user1_id), true);
    assert.equal(pmc.is_partner(user2_id), false);
    assert.equal(pmc.is_partner(user3_id), true);
});

test("insert_recent_private_message", () => {
    pmc.recent.initialize(params);

    // Base data
    assert.deepEqual(pmc.recent.get(), [
        {user_ids_string: "1", max_message_id: 100},
        {user_ids_string: "3", max_message_id: 99},
        {user_ids_string: "1,2", max_message_id: 98},
        {user_ids_string: "1,2,3", max_message_id: 97},
        {user_ids_string: "15", max_message_id: 96},
    ]);

    // Insert new messages (which should rearrange these entries).
    pmc.recent.insert([1], 1000);
    pmc.recent.insert([1, 2, 3], 999);
    // direct message to oneself
    pmc.recent.insert([], 101);

    // Try to backdate user1's latest message.
    pmc.recent.insert([1], 555);

    assert.deepEqual(pmc.recent.get(), [
        {user_ids_string: "1", max_message_id: 1000},
        {user_ids_string: "1,2,3", max_message_id: 999},
        {user_ids_string: "15", max_message_id: 101},
        {user_ids_string: "3", max_message_id: 99},
        {user_ids_string: "1,2", max_message_id: 98},
    ]);
    assert.deepEqual(pmc.recent.get_strings(), ["1", "1,2,3", "15", "3", "1,2"]);
});

test("muted_users", () => {
    pmc.recent.initialize(params);

    // Base data
    assert.deepEqual(pmc.recent.get(), [
        {user_ids_string: "1", max_message_id: 100},
        {user_ids_string: "3", max_message_id: 99},
        {user_ids_string: "1,2", max_message_id: 98},
        {user_ids_string: "1,2,3", max_message_id: 97},
        {user_ids_string: "15", max_message_id: 96},
    ]);
    assert.deepEqual(pmc.recent.get_strings(), ["1", "3", "1,2", "1,2,3", "15"]);

    // Mute some users.
    muted_users.add_muted_user(1);
    muted_users.add_muted_user(2);

    // We should now get back only those messages which are either-
    // 1:1 direct messages in which the other user hasn't been muted.
    // Direct message groups where there's at least one non-muted participant.
    assert.deepEqual(pmc.recent.get(), [
        {user_ids_string: "3", max_message_id: 99},
        {user_ids_string: "1,2,3", max_message_id: 97},
        {user_ids_string: "15", max_message_id: 96},
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
