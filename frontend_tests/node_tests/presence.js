zrequire('people');
zrequire('presence');

set_global('server_events', {});
set_global('blueslip', {});

var OFFLINE_THRESHOLD_SECS = 140;

var me = {
    email: 'me@zulip.com',
    user_id: 999,
    full_name: 'Me Myself',
};

var alice = {
    email: 'alice@zulip.com',
    user_id: 1,
    full_name: 'Alice Smith',
};

var fred = {
    email: 'fred@zulip.com',
    user_id: 2,
    full_name: "Fred Flintstone",
};

var zoe = {
    email: 'zoe@example.com',
    user_id: 6,
    full_name: 'Zoe Yang',
};

var bot = {
    email: 'bot@zulip.com',
    user_id: 7,
    full_name: 'The Bot',
    is_bot: true,
};

people.add_in_realm(me);
people.add_in_realm(alice);
people.add_in_realm(fred);
people.add_in_realm(zoe);
people.add_in_realm(bot);
people.initialize_current_user(me.user_id);

(function test_on_mobile_property() {
    // TODO: move this test to a new test module directly testing presence.js
    var status_from_timestamp = presence._status_from_timestamp;

    var base_time = 500;
    var info = {
        website: {
            status: "active",
            timestamp: base_time,
        },
    };
    var status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS - 1, info);
    assert.equal(status.mobile, false);

    info.Android = {
        status: "active",
        timestamp: base_time + OFFLINE_THRESHOLD_SECS / 2,
        pushable: false,
    };
    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS, info);
    assert.equal(status.mobile, true);
    assert.equal(status.status, "active");

    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS - 1, info);
    assert.equal(status.mobile, false);
    assert.equal(status.status, "active");

    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS * 2, info);
    assert.equal(status.mobile, false);
    assert.equal(status.status, "offline");

    info.Android = {
        status: "idle",
        timestamp: base_time + OFFLINE_THRESHOLD_SECS / 2,
        pushable: true,
    };
    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS, info);
    assert.equal(status.mobile, true);
    assert.equal(status.status, "idle");

    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS - 1, info);
    assert.equal(status.mobile, false);
    assert.equal(status.status, "active");

    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS * 2, info);
    assert.equal(status.mobile, true);
    assert.equal(status.status, "offline");

    info.Android = {
        status: "offline",
        timestamp: base_time + OFFLINE_THRESHOLD_SECS / 2,
        pushable: true,
    };
    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS, info);
    assert.equal(status.mobile, true);
    assert.equal(status.status, "offline");

    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS - 1, info);
    assert.equal(status.mobile, false);
    assert.equal(status.status, "active"); // website

    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS * 2, info);
    assert.equal(status.mobile, true);
    assert.equal(status.status, "offline");

    info.Android = {
        status: "unknown",
        timestamp: base_time + OFFLINE_THRESHOLD_SECS / 2,
        pushable: true,
    };
    var called = false;
    blueslip.error = function () {
        assert.equal(arguments[0], 'Unexpected status');
        assert.deepEqual(arguments[1].presence_object, info.Android);
        assert.equal(arguments[2], undefined);
        called = true;
    };
    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS - 1, info);
    assert.equal(status.mobile, false);
    assert.equal(status.status, "active"); // website
    assert(called);
}());

(function test_set_presence_info() {
    var presences = {};
    var base_time = 500;

    presences[alice.email] = {
        website: {
            status: 'active',
            timestamp: base_time,
        },
    };

    presences[fred.email] = {
        website: {
            status: 'idle',
            timestamp: base_time,
        },
    };

    presence.set_info(presences, base_time);

    assert.deepEqual(presence.presence_info[alice.user_id],
        { status: 'active', mobile: false, last_active: 500}
    );

    assert.deepEqual(presence.presence_info[fred.user_id],
        { status: 'idle', mobile: false, last_active: 500}
    );

    assert.deepEqual(presence.presence_info[zoe.user_id],
        { status: 'offline', mobile: false, last_active: undefined}
    );

    assert(!presence.presence_info[bot.user_id]);

    // Make it seem like realm has a lot of people
    var get_realm_count = people.get_realm_count;
    people.get_realm_count = function () { return 1000; };
    assert.equal(presence.set_info(presences, base_time), undefined);
    people.get_realm_count = get_realm_count;

    var unknown = {
        email: 'unknown@zulip.com',
        user_id: 42,
        full_name: 'Unknown Name',
    };
    presences[unknown.email] = {};

    server_events.suspect_offline = false;
    blueslip.error = function (msg) {
        assert.equal(msg, 'Unknown email in presence data: unknown@zulip.com');
    };
    presence.set_info(presences, base_time);
}());

(function test_last_active_date() {
    var unknown_id = 42;
    presence.presence_info = {
        1: { last_active: 500 }, // alice.user_id
        2: {}, // fred.user_id
    };
    set_global('XDate', function (ms) { return {seconds: ms}; });

    assert.equal(presence.last_active_date(unknown_id), undefined);
    assert.equal(presence.last_active_date(fred.user_id), undefined);
    assert.deepEqual(presence.last_active_date(alice.user_id), {seconds: 500000});
}());

(function test_set_user_status() {
    var server_time = 500;
    var info = {
        website: {
            status: "active",
            timestamp: server_time,
        },
    };

    presence.presence_info[alice.user_id] = undefined;
    presence.set_user_status(alice.user_id, info, server_time);

    var expected = { status: 'active', mobile: false, last_active: 500 };
    assert.deepEqual(presence.presence_info[alice.user_id], expected);
}());

