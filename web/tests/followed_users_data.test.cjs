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

test("multiple_simultaneous_follows", () => {
    const user_ids = [1, 2, 3, 4, 5];

    // Add multiple users
    user_ids.forEach((id) => {
        followed_users_data.add_followed_user(id);
    });

    // Verify all are followed
    user_ids.forEach((id) => {
        assert.ok(followed_users_data.is_user_followed(id));
    });

    // Verify others are not followed
    assert.ok(!followed_users_data.is_user_followed(99));
    assert.ok(!followed_users_data.is_user_followed(100));
});

test("add_with_timestamps", () => {
    const timestamp1 = 1577836800;
    const timestamp2 = 1577836900;

    followed_users_data.add_followed_user(1, timestamp1);
    followed_users_data.add_followed_user(2, timestamp2);

    assert.ok(followed_users_data.is_user_followed(1));
    assert.ok(followed_users_data.is_user_followed(2));
});

test("selective_remove_with_multiple_follows", () => {
    const user_ids = [5, 10, 15, 20, 25];

    // Add multiple users
    user_ids.forEach((id) => {
        followed_users_data.add_followed_user(id);
    });

    // Remove some users
    followed_users_data.remove_followed_user(10);
    followed_users_data.remove_followed_user(20);

    // Verify correct state
    assert.ok(followed_users_data.is_user_followed(5));
    assert.ok(!followed_users_data.is_user_followed(10));
    assert.ok(followed_users_data.is_user_followed(15));
    assert.ok(!followed_users_data.is_user_followed(20));
    assert.ok(followed_users_data.is_user_followed(25));
});

test("set_followed_users_replaces_state", () => {
    // Add some users
    followed_users_data.add_followed_user(1);
    followed_users_data.add_followed_user(2);
    assert.ok(followed_users_data.is_user_followed(1));
    assert.ok(followed_users_data.is_user_followed(2));

    // Replace with different set
    followed_users_data.set_followed_users([
        {id: 99, timestamp: 1577836800},
        {id: 100, timestamp: 1577836800},
    ]);

    // Old users should not be followed
    assert.ok(!followed_users_data.is_user_followed(1));
    assert.ok(!followed_users_data.is_user_followed(2));

    // New users should be followed
    assert.ok(followed_users_data.is_user_followed(99));
    assert.ok(followed_users_data.is_user_followed(100));
});

test("follow_unfollow_refollow_cycle", () => {
    const user_id = 7;

    // Follow
    followed_users_data.add_followed_user(user_id);
    assert.ok(followed_users_data.is_user_followed(user_id));

    // Unfollow
    followed_users_data.remove_followed_user(user_id);
    assert.ok(!followed_users_data.is_user_followed(user_id));

    // Re-follow
    followed_users_data.add_followed_user(user_id);
    assert.ok(followed_users_data.is_user_followed(user_id));

    // Unfollow again
    followed_users_data.remove_followed_user(user_id);
    assert.ok(!followed_users_data.is_user_followed(user_id));
});

test("edge_case_with_null_and_false", () => {
    // These should be handled gracefully
    assert.ok(!followed_users_data.is_user_followed(null));
    assert.ok(!followed_users_data.is_user_followed(false));

    // Valid user should still work
    followed_users_data.add_followed_user(1);
    assert.ok(followed_users_data.is_user_followed(1));
});
