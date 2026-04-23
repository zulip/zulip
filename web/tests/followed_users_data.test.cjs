"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const followed_users_data = zrequire("followed_users_data");

function test(label, f) {
    run_test(label, ({override}) => {
        followed_users_data.set_followed_users([]);
        f({override});
    });
}

test("edge_cases", () => {
    // Undefined and falsy user IDs should never be considered followed.
    assert.ok(!followed_users_data.is_user_followed(undefined));
    assert.ok(!followed_users_data.is_user_followed(0));
});

test("add_and_remove_follows", () => {
    assert.ok(!followed_users_data.is_user_followed(1));

    followed_users_data.add_followed_user(1);
    assert.ok(followed_users_data.is_user_followed(1));

    // Adding the same user again should be idempotent.
    followed_users_data.add_followed_user(1);
    assert.ok(followed_users_data.is_user_followed(1));

    followed_users_data.remove_followed_user(1);
    assert.ok(!followed_users_data.is_user_followed(1));

    // Removing a user not in the list should be idempotent.
    followed_users_data.remove_followed_user(1);
    assert.ok(!followed_users_data.is_user_followed(1));
});

test("set_followed_users", () => {
    followed_users_data.set_followed_users([
        {id: 3, timestamp: 1577836800},
        {id: 7, timestamp: 1577836800},
    ]);

    assert.ok(followed_users_data.is_user_followed(3));
    assert.ok(followed_users_data.is_user_followed(7));
    assert.ok(!followed_users_data.is_user_followed(1));

    // Calling set_followed_users replaces the list entirely.
    followed_users_data.set_followed_users([]);
    assert.ok(!followed_users_data.is_user_followed(3));
    assert.ok(!followed_users_data.is_user_followed(7));
});

test("initialize", () => {
    followed_users_data.initialize({
        followed_users: [
            {id: 4, timestamp: 1577836800},
            {id: 2, timestamp: 1577836800},
        ],
    });

    assert.ok(followed_users_data.is_user_followed(4));
    assert.ok(followed_users_data.is_user_followed(2));
    assert.ok(!followed_users_data.is_user_followed(99));
});
