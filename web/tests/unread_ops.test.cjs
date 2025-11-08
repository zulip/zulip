"use strict";

const assert = require("node:assert/strict");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

set_global("document", {hasFocus: () => true});
const unread = zrequire("unread");
const unread_ops = zrequire("unread_ops");

run_test("get_message_count_text", () => {
    unread.set_old_unreads_missing_for_tests(true);
    assert.equal(
        unread_ops.get_message_count_text(5),
        "translated: 5+ messages will be marked as read.",
    );
    assert.equal(
        unread_ops.get_message_count_text(1),
        "translated: 1+ messages will be marked as read.",
    );

    unread.set_old_unreads_missing_for_tests(false);
    assert.equal(
        unread_ops.get_message_count_text(5),
        "translated: 5 messages will be marked as read.",
    );
    assert.equal(
        unread_ops.get_message_count_text(1),
        "translated: 1 message will be marked as read.",
    );
});
