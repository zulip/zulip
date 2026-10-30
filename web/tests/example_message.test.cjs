"use strict";

const assert = require("node:assert/strict");

const {make_channel_message, make_direct_message} = require("./lib/example_message.cjs");
const {make_stream} = require("./lib/example_stream.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const people = zrequire("people");
const stream_data = zrequire("stream_data");

run_test("make_channel_message: basic fields", () => {
    const alice = make_user({email: "alice@zulip.com", user_id: 1, full_name: "Alice Smith"});
    people.add_active_user(alice);

    const denmark = make_stream({name: "Denmark", stream_id: 10});
    stream_data.add_sub_for_tests(denmark);

    const msg = make_channel_message({
        stream_id: 10,
        subject: "topic",
        sender_id: 1,
    });
    assert.equal(msg.type, "stream");
    assert.equal(msg.stream_id, 10);
    assert.equal(msg.subject, "topic");
    assert.equal(msg.sender_id, 1);
    assert.equal(msg.sender_email, "alice@zulip.com");
    assert.equal(msg.sender_full_name, "Alice Smith");
    assert.equal(msg.display_recipient, "Denmark");
    assert.ok(msg.id);
});

run_test("make_direct_message: basic fields", () => {
    const alice = make_user({email: "alice@zulip.com", user_id: 1, full_name: "Alice Smith"});
    people.add_active_user(alice);

    const msg = make_direct_message({
        sender_id: 1,
        display_recipient: [{id: 1}, {id: 2}],
    });
    assert.equal(msg.type, "private");
    assert.equal(msg.sender_id, 1);
    assert.equal(msg.sender_email, "alice@zulip.com");
    assert.equal(msg.sender_full_name, "Alice Smith");
    assert.deepEqual(msg.display_recipient, [{id: 1}, {id: 2}]);
    assert.ok(msg.id);
});
