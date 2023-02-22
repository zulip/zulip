"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const {page_params} = require("./lib/zpage_params");

const people = zrequire("people");
const stream_create_subscribers_data = zrequire("stream_create_subscribers_data");

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
        page_params.is_admin = false;
        people.init();
        people.add_active_user(me);
        people.add_active_user(test_user101);
        people.add_active_user(test_user102);
        people.add_active_user(test_user103);
        page_params.user_id = me.user_id;
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

    assert.ok(stream_create_subscribers_data.must_be_subscribed(me.user_id));
    assert.ok(!stream_create_subscribers_data.must_be_subscribed(test_user101.user_id));
});

test("must_be_subscribed", () => {
    page_params.is_admin = false;
    assert.ok(stream_create_subscribers_data.must_be_subscribed(me.user_id));
    assert.ok(!stream_create_subscribers_data.must_be_subscribed(test_user101.user_id));
    page_params.is_admin = true;
    assert.ok(!stream_create_subscribers_data.must_be_subscribed(me.user_id));
    assert.ok(!stream_create_subscribers_data.must_be_subscribed(test_user101.user_id));
});
