var pmc = zrequire('pm_conversations');

(function test_partners() {
    var user1_id = 1;
    var user2_id = 2;
    var user3_id = 3;

    pmc.set_partner(user1_id);
    pmc.set_partner(user3_id);

    assert.equal(pmc.is_partner(user1_id), true);
    assert.equal(pmc.is_partner(user2_id), false);
    assert.equal(pmc.is_partner(user3_id), true);
}());

(function test_insert_recent_private_message() {
    pmc.recent.insert('1', 1001);
    pmc.recent.insert('2', 2001);
    pmc.recent.insert('1', 3001);

    // try to backdate user1's timestamp
    pmc.recent.insert('1', 555);

    assert.deepEqual(pmc.recent.get(), [
        {user_ids_string: '1', timestamp: 3001},
        {user_ids_string: '2', timestamp: 2001},
    ]);

    assert.deepEqual(pmc.recent.get_strings(), ['1', '2']);
}());

