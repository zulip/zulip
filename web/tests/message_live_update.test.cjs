"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const message_lists = mock_esm("../src/message_lists");
const message_store = mock_esm("../src/message_store");

const message_live_update = zrequire("message_live_update");

run_test("update_full_names_and_avatars", ({override}) => {
    const users = [
        {user_id: 1, full_name: "Alice"},
        {user_id: 2, full_name: "Bob"},
    ];

    let updated_senders;
    override(message_store, "update_user_fields", (users) => {
        updated_senders = users;
    });

    const rerendered_messages = [];
    function make_list(messages) {
        return {
            data: {
                get_messages_involving_users(user_ids) {
                    assert.deepEqual([...user_ids], [1, 2]);
                    return messages;
                },
            },
            view: {
                rerender_senders_and_dm_recipient_bars(messages) {
                    rerendered_messages.push(messages);
                },
            },
        };
    }
    const messages_involving_users = [{id: 10}, {id: 11}];
    override(message_lists, "all_rendered_message_lists", () => [
        make_list(messages_involving_users),
        make_list([]),
    ]);

    message_live_update.update_full_names_and_avatars(users);
    assert.deepEqual(updated_senders, users);
    // A list with no messages involving the users isn't rerendered.
    assert.deepEqual(rerendered_messages, [messages_involving_users]);
});
