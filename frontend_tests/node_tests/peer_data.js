"use strict";

/*
    This mostly tests the peer_data module, but it
    also tests some stream_data functions that are
    glorified wrappers for peer_data functions.
*/

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const peer_data = zrequire("peer_data");
const people = zrequire("people");
zrequire("hash_util");
zrequire("stream_data");

set_global("page_params", {
    is_admin: false,
    realm_users: [],
    is_guest: false,
});

const me = {
    email: "me@zulip.com",
    full_name: "Current User",
    user_id: 100,
};

// set up user data
const fred = {
    email: "fred@zulip.com",
    full_name: "Fred",
    user_id: 101,
};
const gail = {
    email: "gail@zulip.com",
    full_name: "Gail",
    user_id: 102,
};
const george = {
    email: "george@zulip.com",
    full_name: "George",
    user_id: 103,
};

people.add_active_user(fred);
people.add_active_user(gail);
people.add_active_user(george);
people.add_active_user(me);
people.initialize_current_user(me.user_id);

const devel = {name: "devel", subscribed: false, stream_id: 1};
const rome = {name: "Rome", subscribed: true, stream_id: 1001};
stream_data.add_sub(devel);
stream_data.add_sub(rome);

function contains_sub(subs, sub) {
    return subs.some((s) => s.name === sub.name);
}

run_test("unsubscribe", () => {
    // verify clean slate
    assert(!stream_data.is_subscribed("devel"));

    // set up our subscription
    devel.subscribed = true;
    peer_data.set_subscribers(devel.stream_id, [me.user_id]);

    // ensure our setup is accurate
    assert(stream_data.is_subscribed("devel"));

    // DO THE UNSUBSCRIBE HERE
    stream_data.unsubscribe_myself(devel);
    assert(!devel.subscribed);
    assert(!stream_data.is_subscribed("devel"));
    assert(!contains_sub(stream_data.subscribed_subs(), devel));
    assert(contains_sub(stream_data.unsubscribed_subs(), devel));

    // make sure subsequent calls work
    const sub = stream_data.get_sub("devel");
    assert(!sub.subscribed);
});

run_test("subscribers", () => {
    const sub = rome;

    // verify setup
    assert(stream_data.is_subscribed(sub.name));

    function potential_subscriber_ids() {
        const users = peer_data.potential_subscribers(sub.stream_id);
        return users.map((u) => u.user_id).sort();
    }

    assert.deepEqual(potential_subscriber_ids(), [
        me.user_id,
        fred.user_id,
        gail.user_id,
        george.user_id,
    ]);

    peer_data.set_subscribers(sub.stream_id, [me.user_id, fred.user_id, george.user_id]);
    stream_data.update_calculated_fields(sub);
    assert(stream_data.is_user_subscribed(sub.stream_id, me.user_id));
    assert(stream_data.is_user_subscribed(sub.stream_id, fred.user_id));
    assert(stream_data.is_user_subscribed(sub.stream_id, george.user_id));
    assert(!stream_data.is_user_subscribed(sub.stream_id, gail.user_id));

    assert.deepEqual(potential_subscriber_ids(), [gail.user_id]);

    peer_data.set_subscribers(sub.stream_id, []);

    const brutus = {
        email: "brutus@zulip.com",
        full_name: "Brutus",
        user_id: 104,
    };
    people.add_active_user(brutus);
    assert(!stream_data.is_user_subscribed(sub.stream_id, brutus.user_id));

    // add
    peer_data.add_subscriber(sub.stream_id, brutus.user_id);
    assert(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id));
    assert.equal(peer_data.get_subscriber_count(sub.stream_id), 1);
    const sub_email = "Rome:214125235@zulipdev.com:9991";
    stream_data.update_stream_email_address(sub, sub_email);
    assert.equal(sub.email_address, sub_email);

    // verify that adding an already-added subscriber is a noop
    peer_data.add_subscriber(sub.stream_id, brutus.user_id);
    assert(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id));
    assert.equal(peer_data.get_subscriber_count(sub.stream_id), 1);

    // remove
    let ok = peer_data.remove_subscriber(sub.stream_id, brutus.user_id);
    assert(ok);
    assert(!stream_data.is_user_subscribed(sub.stream_id, brutus.user_id));
    assert.equal(peer_data.get_subscriber_count(sub.stream_id), 0);

    // verify that checking subscription with undefined user id

    blueslip.expect("warn", "Undefined user_id passed to function is_user_subscribed");
    assert.equal(stream_data.is_user_subscribed(sub.stream_id, undefined), undefined);
    blueslip.reset();

    // Verify noop for bad stream when removing subscriber
    const bad_stream_id = 999999;
    blueslip.expect("warn", "We called get_user_set for an untracked stream: " + bad_stream_id);
    blueslip.expect("warn", "We tried to remove invalid subscriber: 104");
    ok = peer_data.remove_subscriber(bad_stream_id, brutus.user_id);
    assert(!ok);
    blueslip.reset();

    // verify that removing an already-removed subscriber is a noop
    blueslip.expect("warn", "We tried to remove invalid subscriber: 104");
    ok = peer_data.remove_subscriber(sub.stream_id, brutus.user_id);
    assert(!ok);
    assert(!stream_data.is_user_subscribed(sub.stream_id, brutus.user_id));
    assert.equal(peer_data.get_subscriber_count(sub.stream_id), 0);
    blueslip.reset();

    // Verify defensive code in set_subscribers, where the second parameter
    // can be undefined.
    stream_data.add_sub(sub);
    peer_data.add_subscriber(sub.stream_id, brutus.user_id);
    sub.subscribed = true;
    assert(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id));

    // Verify that we noop and don't crash when unsubscribed.
    sub.subscribed = false;
    stream_data.update_calculated_fields(sub);
    peer_data.add_subscriber(sub.stream_id, brutus.user_id);
    assert.equal(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id), true);
    peer_data.remove_subscriber(sub.stream_id, brutus.user_id);
    assert.equal(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id), false);
    peer_data.add_subscriber(sub.stream_id, brutus.user_id);
    assert.equal(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id), true);

    blueslip.expect(
        "warn",
        "We got a is_user_subscribed call for a non-existent or inaccessible stream.",
        2,
    );
    sub.invite_only = true;
    stream_data.update_calculated_fields(sub);
    assert.equal(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id), undefined);
    peer_data.remove_subscriber(sub.stream_id, brutus.user_id);
    assert.equal(stream_data.is_user_subscribed(sub.stream_id, brutus.user_id), undefined);
    blueslip.reset();

    // Verify that we don't crash for a bad stream.
    blueslip.expect("warn", "We called get_user_set for an untracked stream: 9999999");
    peer_data.add_subscriber(9999999, brutus.user_id);
    blueslip.reset();

    // Verify that we don't crash for a bad user id.
    blueslip.expect("error", "Unknown user_id in get_by_user_id: 88888");
    blueslip.expect("warn", "We tried to add invalid subscriber: 88888");
    peer_data.add_subscriber(sub.stream_id, 88888);
    blueslip.reset();
});

run_test("get_subscriber_count", () => {
    const india = {
        stream_id: 102,
        name: "India",
        subscribed: true,
    };
    stream_data.clear_subscriptions();

    blueslip.expect("warn", "We called get_user_set for an untracked stream: 102");
    assert.equal(peer_data.get_subscriber_count(india.stream_id), 0);

    stream_data.add_sub(india);
    assert.equal(peer_data.get_subscriber_count(india.stream_id), 0);

    peer_data.add_subscriber(india.stream_id, fred.user_id);
    assert.equal(peer_data.get_subscriber_count(india.stream_id), 1);
    peer_data.add_subscriber(india.stream_id, george.user_id);
    assert.equal(peer_data.get_subscriber_count(india.stream_id), 2);

    peer_data.remove_subscriber(india.stream_id, george.user_id);
    assert.deepStrictEqual(peer_data.get_subscriber_count(india.stream_id), 1);
});

run_test("is_subscriber_subset", () => {
    function make_sub(stream_id, user_ids) {
        const sub = {
            stream_id,
            name: `stream ${stream_id}`,
        };
        stream_data.add_sub(sub);
        peer_data.set_subscribers(sub.stream_id, user_ids);
        return sub;
    }

    const sub_a = make_sub(301, [1, 2]);
    const sub_b = make_sub(302, [2, 3]);
    const sub_c = make_sub(303, [1, 2, 3]);

    const matrix = [
        [sub_a, sub_a, true],
        [sub_a, sub_b, false],
        [sub_a, sub_c, true],
        [sub_b, sub_a, false],
        [sub_b, sub_b, true],
        [sub_b, sub_c, true],
        [sub_c, sub_a, false],
        [sub_c, sub_b, false],
        [sub_c, sub_c, true],
    ];

    for (const row of matrix) {
        assert.equal(peer_data.is_subscriber_subset(row[0].stream_id, row[1].stream_id), row[2]);
    }

    // Two untracked streams should never be passed into us.
    blueslip.expect("warn", "We called get_user_set for an untracked stream: 88888");
    blueslip.expect("warn", "We called get_user_set for an untracked stream: 99999");
    peer_data.is_subscriber_subset(99999, 88888);
    blueslip.reset();

    // Warn about hypothetical undefined stream_ids.
    blueslip.expect("error", "You must pass ids as numbers to peer_data. id = undefined");
    blueslip.expect("warn", "We called get_user_set for an untracked stream: undefined");
    peer_data.is_subscriber_subset(undefined, sub_a.stream_id);
    blueslip.reset();
});
