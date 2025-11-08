"use strict";

const assert = require("node:assert/strict");

const _ = require("lodash");

const {make_user, make_bot} = require("./lib/example_user.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const people = zrequire("people");
const {ConversationParticipants} = zrequire("../src/conversation_participants.ts");

const user1 = make_user();
const user2 = make_user();
const bot1 = make_bot();
const bot2 = make_bot();

people._add_user(user1);
people._add_user(user2);
people._add_user(bot1);
people._add_user(bot2);

const human_messages = [
    {
        id: 1,
        sender_id: user1.user_id,
        sent_by_me: true,
    },
    {
        id: 2,
        sender_id: user2.user_id,
        sent_by_me: false,
    },
];

const bot_messages = [
    {
        id: 4,
        sender_id: bot1.user_id,
        sent_by_me: false,
    },
    {
        id: 5,
        sender_id: bot2.user_id,
        sent_by_me: false,
    },
];

const all_messages = [...human_messages, ...bot_messages];

run_test("Add participants", () => {
    const participants = new ConversationParticipants(all_messages);
    assert.ok(_.isEqual(participants.humans, new Set([user1.user_id, user2.user_id])));
    assert.ok(_.isEqual(participants.bots, new Set([bot1.user_id, bot2.user_id])));
    // None since they were not added as active users.
    assert.equal(participants.visible().size, 0);

    // Add user1 as active user.
    people.add_active_user(user1);
    assert.ok(_.isEqual(participants.visible(), new Set([user1.user_id])));
});
