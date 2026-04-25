"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const user_tasks_assignment = zrequire("user_tasks_assignment");

run_test("resolve_assignee_email prefers delivery_email", () => {
    const email = user_tasks_assignment.resolve_assignee_email({
        delivery_email: "zoe@example.com",
        email: "zoe+legacy@example.com",
    });

    assert.equal(email, "zoe@example.com");
});

run_test("resolve_assignee_email falls back to email", () => {
    const email = user_tasks_assignment.resolve_assignee_email({
        email: "zoe@example.com",
    });

    assert.equal(email, "zoe@example.com");
});

run_test("resolve_assignee_email returns empty string when unavailable", () => {
    const email = user_tasks_assignment.resolve_assignee_email({
        full_name: "Zoe",
    });

    assert.equal(email, "");
});

run_test("resolve_assignee_email ignores whitespace-only fields", () => {
    const email = user_tasks_assignment.resolve_assignee_email({
        delivery_email: "   ",
        email: "   ",
    });

    assert.equal(email, "");
});
