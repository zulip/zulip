zrequire('people');
zrequire('presence');

const return_false = function () { return false; };

set_global('server_events', {});
set_global('blueslip', {});
set_global('page_params', {});
set_global('reload_state', {
    is_in_progress: return_false,
});

const OFFLINE_THRESHOLD_SECS = 140;

const me = {
    email: 'me@zulip.com',
    user_id: 999,
    full_name: 'Me Myself',
};

const alice = {
    email: 'alice@zulip.com',
    user_id: 1,
    full_name: 'Alice Smith',
};

const fred = {
    email: 'fred@zulip.com',
    user_id: 2,
    full_name: "Fred Flintstone",
};

const zoe = {
    email: 'zoe@example.com',
    user_id: 6,
    full_name: 'Zoe Yang',
};

const bot = {
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

run_test('my user', () => {
    assert.equal(presence.get_status(me.user_id), 'active');
});

run_test('status_from_timestamp', () => {
    const status_from_timestamp = presence._status_from_timestamp;

    const base_time = 500;
    const info = {
        website: {
            status: "active",
            timestamp: base_time,
        },
    };
    let status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS - 1, info);

    info.random_client = {
        status: "active",
        timestamp: base_time + OFFLINE_THRESHOLD_SECS / 2,
        pushable: false,
    };
    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS, info);
    assert.equal(status.status, "active");

    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS - 1, info);
    assert.equal(status.status, "active");

    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS * 2, info);
    assert.equal(status.status, "offline");

    info.random_client = {
        status: "idle",
        timestamp: base_time + OFFLINE_THRESHOLD_SECS / 2,
        pushable: true,
    };
    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS, info);
    assert.equal(status.status, "idle");

    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS - 1, info);
    assert.equal(status.status, "active");

    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS * 2, info);
    assert.equal(status.status, "offline");

    info.random_client = {
        status: "offline",
        timestamp: base_time + OFFLINE_THRESHOLD_SECS / 2,
        pushable: true,
    };
    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS, info);
    assert.equal(status.status, "offline");

    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS - 1, info);
    assert.equal(status.status, "active"); // website

    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS * 2, info);
    assert.equal(status.status, "offline");

    info.random_client = {
        status: "unknown",
        timestamp: base_time + OFFLINE_THRESHOLD_SECS / 2,
        pushable: true,
    };
    let called = false;
    blueslip.error = function () {
        assert.equal(arguments[0], 'Unexpected status');
        assert.deepEqual(arguments[1].presence_object, info.random_client);
        assert.equal(arguments[2], undefined);
        called = true;
    };
    status = status_from_timestamp(
        base_time + OFFLINE_THRESHOLD_SECS - 1, info);
    assert.equal(status.status, "active"); // website
    assert(called);
});

run_test('set_presence_info', () => {
    const presences = {};
    const base_time = 500;

    presences[alice.user_id.toString()] = {
        website: {
            status: 'active',
            timestamp: base_time,
        },
    };

    presences[fred.user_id.toString()] = {
        website: {
            status: 'idle',
            timestamp: base_time,
        },
    };

    presences[me.user_id.toString()] = {
        website: {
            status: 'active',
            timestamp: base_time,
        },
    };

    page_params.presences = presences;
    page_params.initial_servertime = base_time;
    presence.initialize();

    assert.equal(page_params.presences, undefined);

    assert.deepEqual(presence.presence_info.get(alice.user_id),
                     { status: 'active', last_active: 500}
    );

    assert.deepEqual(presence.presence_info.get(fred.user_id),
                     { status: 'idle', last_active: 500}
    );

    assert.deepEqual(presence.presence_info.get(me.user_id),
                     { status: 'active', last_active: 500}
    );

    assert.deepEqual(presence.presence_info.get(zoe.user_id),
                     { status: 'offline', last_active: undefined}
    );

    assert(!presence.presence_info.has(bot.user_id));

    // Make it seem like realm has a lot of people
    const get_realm_count = people.get_realm_count;
    people.get_realm_count = function () { return 1000; };
    assert.equal(presence.set_info(presences, base_time), undefined);
    people.get_realm_count = get_realm_count;
});

run_test('last_active_date', () => {
    const unknown_id = 42;
    presence.presence_info.clear();
    presence.presence_info.set(alice.user_id, { last_active: 500 });
    presence.presence_info.set(fred.user_id, {});
    set_global('XDate', function (ms) { return {seconds: ms}; });

    assert.equal(presence.last_active_date(unknown_id), undefined);
    assert.equal(presence.last_active_date(fred.user_id), undefined);
    assert.deepEqual(presence.last_active_date(alice.user_id), {seconds: 500000});
});

run_test('update_info_from_event', () => {
    const server_time = 500;
    const info = {
        website: {
            status: "active",
            timestamp: server_time,
        },
    };

    presence.presence_info.delete(alice.user_id);
    presence.update_info_from_event(alice.user_id, info, server_time);

    const expected = { status: 'active', last_active: 500 };
    assert.deepEqual(presence.presence_info.get(alice.user_id), expected);
});
