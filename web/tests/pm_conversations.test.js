"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const {current_user} = require("./lib/zpage_params");

const user_topics = zrequire("user_topics");
const muted_users = zrequire("muted_users");
const message_lists = zrequire("message_lists");
const {Filter} = zrequire("../src/filter");
const people = zrequire("people");
const pmc = zrequire("pm_conversations");

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

const params = {
    recent_private_conversations: [
        {user_ids: [alice.user_id], max_message_id: 100},
        {user_ids: [alex.user_id], max_message_id: 99},
        {user_ids: [alice.user_id, isaac.user_id], max_message_id: 98},
        {user_ids: [alice.user_id, isaac.user_id, alex.user_id], max_message_id: 97},
        {user_ids: [me.user_id], max_message_id: 96}, // self
    ],
};

function set_filter(raw_terms) {
    const terms = raw_terms.map((op) => ({
        operator: op[0],
        operand: op[1],
    }));
    const filter = new Filter(terms);
    message_lists.set_current({
        data: {
            filter,
        },
    });

    return filter;
}

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

test("has_conversation", () => {
    current_user.user_id = me.user_id;
    pmc.recent.initialize(params);

    people.add_active_user(alice);
    people.add_active_user(isaac);
    people.add_active_user(alex);
    people.add_active_user(me);

    // Tests if `has_conversation` returns `true` when there are previous
    // messages in the conversation.
    assert.ok(pmc.recent.has_conversation("1"));
    assert.ok(pmc.recent.has_conversation("15"));
    assert.ok(pmc.recent.has_conversation("1,2"));
    assert.ok(pmc.recent.has_conversation("1,2,15"));

    // Since the current filter does not match the DM view, there may be
    // messages in the conversation which are not fetched yet.
    assert.ok(pmc.recent.has_conversation("1,3") === undefined);

    // Tests if `has_conversation` returns `false` when there are no
    // previous messages and the current filter matches the DM view.
    set_filter([["dm", `${alice.email},${alex.email}`]]);
    assert.ok(pmc.recent.has_conversation("1,3") === false);

    set_filter([["dm", `${isaac.email},${me.email}`]]);
    assert.ok(pmc.recent.has_conversation("2") === false);

    // Tests if `has_conversation` returns `undefined` when current filter
    // is set to a different DM view.
    set_filter([["dm", `${alice.email}`]]);
    assert.ok(pmc.recent.has_conversation("1,3") === undefined);
});
