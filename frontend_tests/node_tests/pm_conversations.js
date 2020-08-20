"use strict";

const pmc = zrequire("pm_conversations");

run_test("partners", () => {
    const user1_id = 1;
    const user2_id = 2;
    const user3_id = 3;

    pmc.set_partner(user1_id);
    pmc.set_partner(user3_id);

    assert.equal(pmc.is_partner(user1_id), true);
    assert.equal(pmc.is_partner(user2_id), false);
    assert.equal(pmc.is_partner(user3_id), true);
});

const people = zrequire("people");

run_test("insert_recent_private_message", () => {
    const params = {
        recent_private_conversations: [
            {user_ids: [11, 2], max_message_id: 150},
            {user_ids: [1], max_message_id: 111},
            {user_ids: [], max_message_id: 7},
        ],
    };
    people.initialize_current_user(15);
    pmc.recent.initialize(params);

    assert.deepEqual(pmc.recent.get(), [
        {user_ids_string: "2,11", max_message_id: 150},
        {user_ids_string: "1", max_message_id: 111},
        {user_ids_string: "15", max_message_id: 7},
    ]);

    pmc.recent.insert([1], 1001);
    pmc.recent.insert([2], 2001);
    pmc.recent.insert([1], 3001);

    // try to backdate user1's latest message
    pmc.recent.insert([1], 555);

    assert.deepEqual(pmc.recent.get(), [
        {user_ids_string: "1", max_message_id: 3001},
        {user_ids_string: "2", max_message_id: 2001},
        {user_ids_string: "2,11", max_message_id: 150},
        {user_ids_string: "15", max_message_id: 7},
    ]);

    assert.deepEqual(pmc.recent.get_strings(), ["1", "2", "2,11", "15"]);
});
