"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const muted_users = zrequire("muted_users");

function test(label, f) {
    run_test(label, ({override}) => {
        muted_users.set_muted_users([]);
        f({override});
    });
}

test("edge_cases", () => {
    // invalid user
    assert.ok(!muted_users.is_user_muted(undefined));
});

test("add_and_remove_mutes", () => {
    assert.ok(!muted_users.is_user_muted(1));
    muted_users.add_muted_user(1);
    assert.ok(muted_users.is_user_muted(1));

    // test idempotency
    muted_users.add_muted_user(1);
    assert.ok(muted_users.is_user_muted(1));

    muted_users.remove_muted_user(1);
    assert.ok(!muted_users.is_user_muted(1));

    // test idempotency
    muted_users.remove_muted_user(1);
    assert.ok(!muted_users.is_user_muted(1));
});

test("get_unmuted_users", () => {
    const hamlet = {
        user_id: 1,
        full_name: "King Hamlet",
    };
    const cordelia = {
        user_id: 2,
        full_name: "Cordelia, Lear's Daughter",
    };
    const othello = {
        user_id: 3,
        full_name: "Othello, Moor of Venice",
    };

    muted_users.add_muted_user(hamlet.user_id);
    muted_users.add_muted_user(cordelia.user_id);

    assert.deepEqual(
        muted_users.filter_muted_user_ids([hamlet.user_id, cordelia.user_id, othello.user_id]),
        [othello.user_id],
    );
    assert.deepEqual(muted_users.filter_muted_users([hamlet, cordelia, othello]), [othello]);
});

test("get_mutes", () => {
    assert.deepEqual(muted_users.get_muted_users(), []);
    muted_users.add_muted_user(6, 1577836800);
    muted_users.add_muted_user(4, 1577836800);
    const all_muted_users = muted_users
        .get_muted_users()
        .sort((a, b) => a.date_muted - b.date_muted);

    assert.deepEqual(all_muted_users, [
        {
            date_muted: 1577836800000,
            date_muted_str: "Jan 1, 2020",
            id: 6,
        },
        {
            date_muted: 1577836800000,
            date_muted_str: "Jan 1, 2020",
            id: 4,
        },
    ]);
});

test("initialize", () => {
    const muted_users_params = {
        muted_users: [
            {id: 3, timestamp: 1577836800},
            {id: 2, timestamp: 1577836800},
        ],
    };

    muted_users.initialize(muted_users_params);

    assert.deepEqual(muted_users.get_muted_users().sort(), [
        {
            date_muted: 1577836800000,
            date_muted_str: "Jan 1, 2020",
            id: 3,
        },
        {
            date_muted: 1577836800000,
            date_muted_str: "Jan 1, 2020",
            id: 2,
        },
    ]);
});
