"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const email_pill = zrequire("email_pill");

function widget_with_text(text) {
    return {
        getCurrentText: () => text,
    };
}

run_test("get_current_email accepts comma-separated addresses", () => {
    const emails = "first@example.com, second@example.com";

    assert.equal(email_pill.get_current_email(widget_with_text(emails)), emails);
});

run_test("get_current_email rejects invalid addresses", () => {
    assert.equal(
        email_pill.get_current_email(widget_with_text("first@example.com, invalid")),
        null,
    );
});
