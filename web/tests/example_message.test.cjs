"use strict";

const assert = require("node:assert/strict");

const {make_stream_message, make_private_message} = require("./lib/example_message.cjs");
const {run_test} = require("./lib/test.cjs");

run_test("make_stream_message: basic fields", () => {
    const msg = make_stream_message({
        stream_id: 10,
        subject: "topic",
        sender_id: 5,
    });

    assert.equal(msg.type, "stream");
    assert.equal(msg.stream_id, 10);
    assert.equal(msg.subject, "topic");
    assert.equal(msg.sender_id, 5);
    assert.ok(msg.id);
});

run_test("make_private_message: basic fields", () => {
    const msg = make_private_message({
        sender_id: 2,
        display_recipient: [{id: 1}, {id: 2}],
    });

    assert.equal(msg.type, "private");
    assert.equal(msg.sender_id, 2);
    assert.deepEqual(msg.display_recipient, [{id: 1}, {id: 2}]);
    assert.ok(msg.id);
});
