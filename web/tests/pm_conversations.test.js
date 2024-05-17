"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const user_topics = zrequire("user_topics");
const muted_users = zrequire("muted_users");
const people = zrequire("people");
const pmc = zrequire("pm_conversations");

const params = {
    recent_private_conversations: [
        {user_ids: [1], max_message_id: 100},
        {user_ids: [3], max_message_id: 99},
        {user_ids: [1, 2], max_message_id: 98},
        {user_ids: [1, 2, 3], max_message_id: 97},
        {user_ids: [15], max_message_id: 96}, // self
    ],
};

function test(label, f) {
    run_test(label, ({override}) => {
        pmc.clear_for_testing();
        user_topics.set_user_topics([]);
        muted_users.set_muted_users([]);
        people.initialize_current_user(15);
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
    // Huddles where there's at least one non-muted participant.
    assert.deepEqual(pmc.recent.get(), [
        {user_ids_string: "3", max_message_id: 99},
        {user_ids_string: "1,2,3", max_message_id: 97},
        {user_ids_string: "15", max_message_id: 96},
    ]);
    assert.deepEqual(pmc.recent.get_strings(), ["3", "1,2,3", "15"]);
});
