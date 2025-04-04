"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const people = zrequire("people");
const {set_current_user} = zrequire("state_data");
const stream_create_subscribers_data = zrequire("stream_create_subscribers_data");

const current_user = {};
set_current_user(current_user);

const me = {
    email: "me@zulip.com",
    full_name: "Zed", // Zed will sort to the top by virtue of being the current user.
    user_id: 400,
};

const test_user101 = {
    email: "test101@zulip.com",
    full_name: "Test User 101",
    user_id: 101,
};

const test_user102 = {
    email: "test102@zulip.com",
    full_name: "Test User 102",
    user_id: 102,
};

const test_user103 = {
    email: "test102@zulip.com",
    full_name: "Test User 103",
    user_id: 103,
};

function test(label, f) {
    run_test(label, (helpers) => {
        helpers.override(current_user, "is_admin", false);
        people.init();
        people.add_active_user(me);
        people.add_active_user(test_user101);
        people.add_active_user(test_user102);
        people.add_active_user(test_user103);
        helpers.override(current_user, "user_id", me.user_id);
        people.initialize_current_user(me.user_id);
        f(helpers);
    });
}

test("basics", () => {
    stream_create_subscribers_data.initialize_with_current_user();

    assert.deepEqual(stream_create_subscribers_data.sorted_user_ids(), [me.user_id]);
    assert.deepEqual(stream_create_subscribers_data.get_principals(), [me.user_id]);

    const all_user_ids = stream_create_subscribers_data.get_all_user_ids();
    assert.deepEqual(all_user_ids, [101, 102, 103, 400]);

    stream_create_subscribers_data.add_user_ids(all_user_ids);
    assert.deepEqual(stream_create_subscribers_data.sorted_user_ids(), [400, 101, 102, 103]);

    stream_create_subscribers_data.remove_user_ids([101, 103]);
    assert.deepEqual(stream_create_subscribers_data.sorted_user_ids(), [400, 102]);
    assert.deepEqual(stream_create_subscribers_data.get_potential_subscribers(), [
        test_user101,
        test_user103,
    ]);
});

test("sync_user_ids", () => {
    stream_create_subscribers_data.initialize_with_current_user();
    stream_create_subscribers_data.sync_user_ids([test_user101.user_id, test_user102.user_id]);
    assert.deepEqual(stream_create_subscribers_data.sorted_user_ids(), [
        test_user101.user_id,
        test_user102.user_id,
    ]);
});

test("soft remove", () => {
    stream_create_subscribers_data.initialize_with_current_user();
    stream_create_subscribers_data.add_user_ids([test_user101.user_id, test_user102.user_id]);

    stream_create_subscribers_data.soft_remove_user_id(test_user102.user_id);
    // sorted_user_ids should still have all the users.
    assert.deepEqual(stream_create_subscribers_data.sorted_user_ids(), [
        me.user_id,
        test_user101.user_id,
        test_user102.user_id,
    ]);
    assert.deepEqual(stream_create_subscribers_data.get_principals(), [
        me.user_id,
        test_user101.user_id,
    ]);
    assert.ok(stream_create_subscribers_data.user_id_in_soft_remove_list(test_user102.user_id));
    assert.ok(!stream_create_subscribers_data.user_id_in_soft_remove_list(test_user101.user_id));

    // Removing a user_id should also remove them from soft remove list.
    stream_create_subscribers_data.remove_user_ids([test_user102.user_id]);
    assert.ok(!stream_create_subscribers_data.user_id_in_soft_remove_list(test_user102.user_id));
    assert.deepEqual(stream_create_subscribers_data.sorted_user_ids(), [
        me.user_id,
        test_user101.user_id,
    ]);
    assert.deepEqual(stream_create_subscribers_data.get_principals(), [
        me.user_id,
        test_user101.user_id,
    ]);

    // Undo soft remove
    stream_create_subscribers_data.soft_remove_user_id(test_user101.user_id);
    assert.deepEqual(stream_create_subscribers_data.sorted_user_ids(), [
        me.user_id,
        test_user101.user_id,
    ]);
    assert.deepEqual(stream_create_subscribers_data.get_principals(), [me.user_id]);

    stream_create_subscribers_data.undo_soft_remove_user_id(test_user101.user_id);
    assert.deepEqual(stream_create_subscribers_data.sorted_user_ids(), [
        me.user_id,
        test_user101.user_id,
    ]);
    assert.deepEqual(stream_create_subscribers_data.get_principals(), [
        me.user_id,
        test_user101.user_id,
    ]);
});
