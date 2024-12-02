"use strict";

const assert = require("node:assert/strict");

const _ = require("lodash");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {ConversationParticipants} = zrequire("../src/conversation_participants.ts");

const human_messages = [
    {
        id: 1,
        sender_id: 1,
        sent_by_me: true,
    },
    {
        id: 2,
        sender_id: 2,
        sent_by_me: false,
    },
    {
        id: 3,
        sender_id: 3, // Deleted user
        sent_by_me: false,
    },
];
const MAX_HUMAN_USER_ID = human_messages.at(-1).sender_id;

const bot_messages = [
    {
        id: 4,
        sender_id: 4,
        sent_by_me: false,
    },
    {
        id: 5,
        sender_id: 5,
        sent_by_me: false,
    },
];

const all_messages = [...human_messages, ...bot_messages];

mock_esm("../src/people.ts", {
    maybe_get_user_by_id(user_id) {
        let is_bot = false;
        let is_human = false;
        if (user_id === 3) {
            // Deleted user
            return undefined;
        } else if (user_id <= MAX_HUMAN_USER_ID) {
            is_human = true;
        } else {
            is_bot = true;
        }

        return {
            is_bot,
            is_human,
        };
    },
});

run_test("Add participants", () => {
    const participants = new ConversationParticipants(all_messages);
    assert.ok(_.isEqual(participants.humans, new Set([1, 2])));
    assert.ok(_.isEqual(participants.bots, new Set([4, 5])));
});
