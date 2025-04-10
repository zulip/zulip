"use strict";

/*
    This mostly tests the peer_data module, but it
    also tests some stream_data functions that are
    glorified wrappers for peer_data functions.
*/

const assert = require("node:assert/strict");

const example_settings = require("./lib/example_settings.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const channel = mock_esm("../src/channel");

const peer_data = zrequire("peer_data");
const people = zrequire("people");
const {set_current_user, set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const user_groups = zrequire("user_groups");

set_current_user({});
const realm = {};
set_realm(realm);

page_params.realm_users = [];
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
const bot_botson = {
    email: "botson-bot@example.com",
    user_id: 35,
    full_name: "Bot Botson",
    is_bot: true,
    role: 300,
};

const nobody_group = {
    name: "Nobody",
    id: 1,
    members: new Set([]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
};

function contains_sub(subs, sub) {
    return subs.some((s) => s.name === sub.name);
}
function test(label, f) {
    run_test(label, ({override}) => {
        peer_data.clear_for_testing();
        stream_data.clear_subscriptions();
        people.init();
        people.add_active_user(me);
        people.initialize_current_user(me.user_id);

        user_groups.initialize({
            realm_user_groups: [nobody_group],
        });
        override(
            realm,
            "server_supported_permission_settings",
            example_settings.server_supported_permission_settings,
        );
        override(realm, "realm_can_access_all_users_group", nobody_group.id);

        return f({override});
    });
}

test("unsubscribe", () => {
    const devel = {name: "devel", subscribed: false, stream_id: 1};
    stream_data.add_sub(devel);

    // verify clean slate
    assert.ok(!stream_data.is_subscribed(devel.stream_id));

    // set up our subscription
    devel.subscribed = true;
    peer_data.set_subscribers(devel.stream_id, [me.user_id]);

    // ensure our setup is accurate
    assert.ok(stream_data.is_subscribed(devel.stream_id));

    // DO THE UNSUBSCRIBE HERE
    stream_data.unsubscribe_myself(devel);
    assert.ok(!devel.subscribed);
    assert.ok(!stream_data.is_subscribed(devel.stream_id));
    assert.ok(!contains_sub(stream_data.subscribed_subs(), devel));
    assert.ok(contains_sub(stream_data.unsubscribed_subs(), devel));

    // make sure subsequent calls work
    const sub = stream_data.get_sub("devel");
    assert.ok(!sub.subscribed);
});

test("subscribers", async () => {
    const sub = {
        name: "Rome",
        subscribed: true,
        stream_id: 1001,
        can_add_subscribers_group: nobody_group.id,
        can_administer_channel_group: nobody_group.id,
        can_subscribe_group: nobody_group.id,
    };
    stream_data.add_sub(sub);

    people.add_active_user(fred);
    people.add_active_user(gail);
    people.add_active_user(george);

    // verify setup
    assert.ok(stream_data.is_subscribed(sub.stream_id));

    const stream_id = sub.stream_id;

    function potential_subscriber_ids() {
        const users = peer_data.potential_subscribers(stream_id);
        return users.map((u) => u.user_id).sort();
    }

    assert.deepEqual(potential_subscriber_ids(), [
        me.user_id,
        fred.user_id,
        gail.user_id,
        george.user_id,
    ]);

    peer_data.set_subscribers(stream_id, [me.user_id, fred.user_id, george.user_id]);
    assert.ok(stream_data.is_user_subscribed(stream_id, me.user_id));
    assert.ok(stream_data.is_user_subscribed(stream_id, fred.user_id));
    assert.ok(stream_data.is_user_subscribed(stream_id, george.user_id));
    assert.ok(!stream_data.is_user_subscribed(stream_id, gail.user_id));

    assert.deepEqual(potential_subscriber_ids(), [gail.user_id]);

    peer_data.set_subscribers(stream_id, []);

    const brutus = {
        email: "brutus@zulip.com",
        full_name: "Brutus",
        user_id: 104,
    };
    people.add_active_user(brutus);
    assert.ok(!stream_data.is_user_subscribed(stream_id, brutus.user_id));

    // add
    peer_data.add_subscriber(stream_id, brutus.user_id);
    assert.ok(stream_data.is_user_subscribed(stream_id, brutus.user_id));
    assert.equal(peer_data.get_subscriber_count(stream_id), 1);

    // verify that adding an already-added subscriber is a noop
    peer_data.add_subscriber(stream_id, brutus.user_id);
    assert.ok(stream_data.is_user_subscribed(stream_id, brutus.user_id));
    assert.equal(peer_data.get_subscriber_count(stream_id), 1);

    // remove
    let ok = peer_data.remove_subscriber(stream_id, brutus.user_id);
    assert.ok(ok);
    assert.ok(!stream_data.is_user_subscribed(stream_id, brutus.user_id));
    assert.equal(peer_data.get_subscriber_count(stream_id), 0);

    // Verify noop for bad stream when removing subscriber
    const bad_stream_id = 999999;
    blueslip.expect(
        "warn",
        "We called get_loaded_subscriber_subset for an untracked stream: " + bad_stream_id,
    );
    blueslip.expect("warn", "We tried to remove invalid subscriber: 104");
    ok = peer_data.remove_subscriber(bad_stream_id, brutus.user_id);
    assert.ok(!ok);
    blueslip.reset();

    // verify that removing an already-removed subscriber is a noop
    blueslip.expect("warn", "We tried to remove invalid subscriber: 104");
    ok = peer_data.remove_subscriber(stream_id, brutus.user_id);
    assert.ok(!ok);
    assert.ok(!stream_data.is_user_subscribed(stream_id, brutus.user_id));
    assert.equal(peer_data.get_subscriber_count(stream_id), 0);
    blueslip.reset();

    // Verify defensive code in set_subscribers, where the second parameter
    // can be undefined.
    stream_data.add_sub(sub);
    peer_data.add_subscriber(stream_id, brutus.user_id);
    sub.subscribed = true;
    assert.ok(stream_data.is_user_subscribed(stream_id, brutus.user_id));

    // Verify that we noop and don't crash when unsubscribed.
    sub.subscribed = false;
    peer_data.add_subscriber(stream_id, brutus.user_id);
    assert.equal(stream_data.is_user_subscribed(stream_id, brutus.user_id), true);
    peer_data.remove_subscriber(stream_id, brutus.user_id);
    assert.equal(stream_data.is_user_subscribed(stream_id, brutus.user_id), false);
    peer_data.add_subscriber(stream_id, brutus.user_id);
    assert.equal(stream_data.is_user_subscribed(stream_id, brutus.user_id), true);

    blueslip.expect(
        "warn",
        "We got a is_user_subscribed call for a non-existent or inaccessible stream.",
        2,
    );
    sub.invite_only = true;
    assert.ok(!stream_data.is_user_subscribed(stream_id, brutus.user_id));
    peer_data.remove_subscriber(stream_id, brutus.user_id);
    assert.ok(!stream_data.is_user_subscribed(stream_id, brutus.user_id));
    blueslip.reset();

    // Same test but for `maybe_fetch_is_user_subscribed`
    blueslip.expect(
        "warn",
        "We got a maybe_fetch_is_user_subscribed call for a non-existent or inaccessible stream.",
        2,
    );
    peer_data.add_subscriber(stream_id, brutus.user_id);
    assert.ok(!(await stream_data.maybe_fetch_is_user_subscribed(stream_id, brutus.user_id)));
    peer_data.remove_subscriber(stream_id, brutus.user_id);
    assert.ok(!(await stream_data.maybe_fetch_is_user_subscribed(stream_id, brutus.user_id)));
    blueslip.reset();

    // Verify that we don't crash for a bad stream.
    blueslip.expect(
        "warn",
        "We called get_loaded_subscriber_subset for an untracked stream: 9999999",
    );
    peer_data.add_subscriber(9999999, brutus.user_id);
    blueslip.reset();

    // Verify that we don't crash for a bad user id.
    blueslip.expect("error", "Unknown user_id in maybe_get_user_by_id");
    blueslip.expect("warn", "We tried to add invalid subscriber: 88888");
    peer_data.add_subscriber(stream_id, 88888);
    blueslip.reset();
});

test("maybe_fetch_stream_subscribers", async () => {
    const india = {
        stream_id: 102,
        name: "India",
        subscribed: true,
    };
    stream_data.add_sub(india);
    let channel_get_calls = 0;
    channel.get = (opts) => {
        assert.equal(opts.url, `/json/streams/${india.stream_id}/members`);
        channel_get_calls += 1;
        return {
            subscribers: [1, 2, 3, 4],
        };
    };

    // Only one of these will do the fetch, and the other will wait
    // for the first fetch to complete.
    const promise1 = peer_data.maybe_fetch_stream_subscribers(india.stream_id);
    const promise2 = peer_data.maybe_fetch_stream_subscribers(india.stream_id);
    await promise1;
    await promise2;
    assert.equal(channel_get_calls, 1);

    peer_data.clear_for_testing();
    const pending_promise = peer_data.maybe_fetch_stream_subscribers(india.stream_id, false);
    peer_data.bulk_add_subscribers({
        stream_ids: [india.stream_id],
        user_ids: [7, 9],
    });
    peer_data.bulk_remove_subscribers({
        stream_ids: [india.stream_id],
        user_ids: [3],
    });
    const subscribers_before_fetch_completes = peer_data.get_subscribers(india.stream_id);
    assert.deepEqual(subscribers_before_fetch_completes, [7, 9]);
    const subscribers_after_fetch = await pending_promise;
    assert.deepEqual([...subscribers_after_fetch.keys()], [1, 2, 4, 7, 9]);

    peer_data.clear_for_testing();
    assert.equal(await peer_data.maybe_fetch_is_user_subscribed(india.stream_id, 2, false), true);
    assert.equal(peer_data.has_full_subscriber_data(india.stream_id), true);

    peer_data.clear_for_testing();
    assert.equal(peer_data.has_full_subscriber_data(india.stream_id), false);
    assert.equal(await peer_data.maybe_fetch_is_user_subscribed(india.stream_id, 2, false), true);
    assert.equal(await peer_data.maybe_fetch_is_user_subscribed(india.stream_id, 5, false), false);

    channel.get = () => {
        throw new Error("error");
    };
    peer_data.clear_for_testing();
    blueslip.expect("error", "Failure fetching channel subscribers");
    assert.equal(await peer_data.maybe_fetch_is_user_subscribed(india.stream_id, 5, false), null);
    // If we know they're subscribed, we return `true` even though we don't have complete
    // data.
    peer_data.bulk_add_subscribers({
        stream_ids: [india.stream_id],
        user_ids: [5],
    });
    assert.equal(await peer_data.maybe_fetch_is_user_subscribed(india.stream_id, 5, false), true);
    blueslip.reset();

    peer_data.clear_for_testing();
    set_global("setTimeout", (f) => {
        f();
    });
    let num_attempts = 0;
    channel.get = async () => {
        num_attempts += 1;
        if (num_attempts === 2) {
            return {
                subscribers: [1, 2, 3, 4],
            };
        }
        throw new Error("error");
    };
    blueslip.expect("error", "Failure fetching channel subscribers");
    const subscribers = await peer_data.maybe_fetch_stream_subscribers_with_retry(india.stream_id);
    assert.equal(num_attempts, 2);
    assert.deepEqual([...subscribers.keys()], [1, 2, 3, 4]);
    blueslip.reset();

    peer_data.clear_for_testing();
    blueslip.expect("error", "Failure fetching channel subscribers");
    num_attempts = 0;
    assert.equal(await peer_data.maybe_fetch_is_user_subscribed(india.stream_id, 5, true), false);
    assert.equal(num_attempts, 2);
});

test("get_subscriber_count", () => {
    people.add_active_user(fred);
    people.add_active_user(gail);
    people.add_active_user(george);
    const welcome_bot = {
        email: "welcome-bot@example.com",
        user_id: 40,
        full_name: "Welcome Bot",
        is_bot: true,
    };
    people.add_active_user(welcome_bot);

    const india = {
        stream_id: 102,
        name: "India",
        subscribed: true,
    };
    stream_data.clear_subscriptions();

    blueslip.expect("warn", "We called get_loaded_subscriber_subset for an untracked stream: 102");
    assert.equal(peer_data.get_subscriber_count(india.stream_id), 0);

    stream_data.add_sub(india);
    assert.equal(peer_data.get_subscriber_count(india.stream_id), 0);

    peer_data.add_subscriber(india.stream_id, fred.user_id);
    assert.equal(peer_data.get_subscriber_count(india.stream_id), 1);
    peer_data.add_subscriber(india.stream_id, george.user_id);
    assert.equal(peer_data.get_subscriber_count(india.stream_id), 2);

    peer_data.remove_subscriber(india.stream_id, george.user_id);
    assert.deepStrictEqual(peer_data.get_subscriber_count(india.stream_id), 1);

    peer_data.add_subscriber(india.stream_id, welcome_bot.user_id);
    assert.deepStrictEqual(peer_data.get_subscriber_count(india.stream_id), 2);
    // Get the count without bots
    assert.deepStrictEqual(peer_data.get_subscriber_count(india.stream_id, false), 1);
});

test("is_subscriber_subset", async () => {
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
        assert.equal(
            await peer_data.is_subscriber_subset(row[0].stream_id, row[1].stream_id),
            row[2],
        );
    }

    // Two untracked streams should never be passed into us.
    blueslip.expect(
        "warn",
        "We called get_loaded_subscriber_subset for an untracked stream: 88888",
    );
    blueslip.expect(
        "warn",
        "We called get_loaded_subscriber_subset for an untracked stream: 99999",
    );
    await peer_data.is_subscriber_subset(99999, 88888);
    blueslip.reset();

    // Warn about hypothetical undefined stream_ids.
    blueslip.expect(
        "warn",
        "We called get_loaded_subscriber_subset for an untracked stream: undefined",
    );
    await peer_data.is_subscriber_subset(undefined, sub_a.stream_id);
    blueslip.reset();

    // Errors when fetching subscriber data return `null`
    channel.get = () => {
        throw new Error("error");
    };
    peer_data.clear_for_testing();
    // Expect two calls, one for each channel
    blueslip.expect("error", "Failure fetching channel subscribers", 2);
    assert.equal(await peer_data.is_subscriber_subset(sub_a.stream_id, sub_b.stream_id), null);
});

test("get_unique_subscriber_count_for_streams", () => {
    const sub = {name: "Rome", subscribed: true, stream_id: 1001};
    stream_data.add_sub(sub);

    people.add_active_user(fred);
    people.add_active_user(gail);
    people.add_active_user(george);
    people.add_active_user(bot_botson);

    const stream_id = sub.stream_id;
    peer_data.set_subscribers(stream_id, [me.user_id, fred.user_id, bot_botson.user_id]);

    const count = peer_data.get_unique_subscriber_count_for_streams([stream_id]);

    assert.equal(count, 2);
});
