add_dependencies({
    people: 'js/people.js',
});

var presence = require('js/presence.js');

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

people.add_in_realm(me);
people.add_in_realm(alice);
people.add_in_realm(fred);
people.add_in_realm(zoe);
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
}());

