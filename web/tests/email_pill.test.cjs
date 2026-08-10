"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const email_pill = zrequire("email_pill");

run_test("get_current_emails", () => {
    let current_text = null;
    const mock_pill_container = {
        getCurrentText: () => current_text,
    };

    // When current text is null
    assert.equal(email_pill.get_current_emails(mock_pill_container), null);

    // Single valid email address
    current_text = "alice@example.com";
    assert.equal(email_pill.get_current_emails(mock_pill_container), "alice@example.com");

    // Multiple comma-separated email addresses
    current_text = "alice@example.com, bob@example.com";
    assert.equal(
        email_pill.get_current_emails(mock_pill_container),
        "alice@example.com, bob@example.com",
    );

    // Comma-separated emails with display names
    current_text = '"Alice Smith" <alice@example.com>, "Bob Jones" <bob@example.com>';
    assert.equal(
        email_pill.get_current_emails(mock_pill_container),
        '"Alice Smith" <alice@example.com>, "Bob Jones" <bob@example.com>',
    );

    // Invalid email input
    current_text = "not-an-email";
    assert.equal(email_pill.get_current_emails(mock_pill_container), null);
});
