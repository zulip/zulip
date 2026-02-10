"use strict";

const assert = require("node:assert/strict");

const {make_user} = require("./lib/example_user.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const direct_message_group_data = zrequire("direct_message_group_data");
const people = zrequire("people");

function create_user(info) {
    const user = make_user(info);
    people.add_active_user(user);
    return user;
}

const me = create_user({
    email: "me@zulip.com",
    user_id: 999,
    full_name: "Me Myself",
});

const alice = create_user({
    email: "alice@zulip.com",
    user_id: 1,
    full_name: "Alice Smith",
});

const fred = create_user({
    email: "fred@zulip.com",
    user_id: 2,
    full_name: "Fred Flintstone",
});

const jill = create_user({
    email: "jill@zulip.com",
    user_id: 3,
    full_name: "Jill Hill",
});

const norbert = create_user({
    email: "norbert@zulip.com",
    user_id: 5,
    full_name: "Norbert Oswald",
});

people.initialize_current_user(me.user_id);

run_test("direct_message_group_data.process_loaded_messages", () => {
    const direct_message_group1 = "jill@zulip.com,norbert@zulip.com";
    const timestamp1 = 1382479029; // older

    const direct_message_group2 = "alice@zulip.com,fred@zulip.com";
    const timestamp2 = 1382479033; // newer

    const old_timestamp = 1382479000;

    const messages = [
        {
            type: "private",
            display_recipient: [{id: jill.user_id}, {id: norbert.user_id}],
            timestamp: timestamp1,
        },
        {
            type: "stream",
        },
        // direct message to myself
        {
            type: "private",
            display_recipient: [{id: me.user_id}],
        },
        {
            type: "private",
            display_recipient: [{id: alice.user_id}, {id: fred.user_id}],
            timestamp: timestamp2,
        },
        {
            type: "private",
            display_recipient: [{id: fred.user_id}, {id: alice.user_id}],
            timestamp: old_timestamp,
        },
    ];

    direct_message_group_data.process_loaded_messages(messages);

    const user_ids_string1 = people.emails_strings_to_user_ids_string(direct_message_group1);
    const user_ids_string2 = people.emails_strings_to_user_ids_string(direct_message_group2);
    assert.deepEqual(direct_message_group_data.get_direct_message_groups(), [
        user_ids_string2,
        user_ids_string1,
    ]);
});
