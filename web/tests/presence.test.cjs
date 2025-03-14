"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => true,
});

const people = zrequire("people");
const presence = zrequire("presence");
const {set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");

const realm = {};
set_realm(realm);
const user_settings = {};
initialize_user_settings({user_settings});

const OFFLINE_THRESHOLD_SECS = 200;

const me = {
    email: "me@zulip.com",
    user_id: 101,
    full_name: "Me Myself",
};

const alice = {
    email: "alice@zulip.com",
    user_id: 1,
    full_name: "Alice Smith",
};

const fred = {
    email: "fred@zulip.com",
    user_id: 2,
    full_name: "Fred Flintstone",
};

const sally = {
    email: "sally@example.com",
    user_id: 3,
    full_name: "Sally Jones",
};

const zoe = {
    email: "zoe@example.com",
    user_id: 6,
    full_name: "Zoe Yang",
};

const bot = {
    email: "bot@zulip.com",
    user_id: 7,
    full_name: "The Bot",
    is_bot: true,
};

const john = {
    email: "john@zulip.com",
    user_id: 8,
    full_name: "John Doe",
    // Second 77.
    date_joined: "1970-01-01 00:01:15 UTC",
};

const jane = {
    email: "jane@zulip.com",
    user_id: 9,
    full_name: "Jane Doe",
};

people.add_active_user(me);
people.add_active_user(alice);
people.add_active_user(fred);
people.add_active_user(sally);
people.add_active_user(zoe);
people.add_active_user(bot);
people.add_active_user(john);
people.add_active_user(jane);

const inaccessible_user_id = 9999;
const inaccessible_user = people.add_inaccessible_user(inaccessible_user_id);
inaccessible_user.is_inaccessible_user = true;

people.initialize_current_user(me.user_id);

function test(label, f) {
    run_test(label, (helpers) => {
        helpers.override(
            realm,
            "server_presence_offline_threshold_seconds",
            OFFLINE_THRESHOLD_SECS,
        );
        helpers.override(user_settings, "presence_enabled", true);
        presence.clear_internal_data();
        f(helpers);
    });
}

test("my user", () => {
    assert.equal(presence.get_status(me.user_id), "active");
});

test("status_from_raw", () => {
    const status_from_raw = presence.status_from_raw;

    const now = 5000;
    let raw;

    raw = {
        server_timestamp: now,
        active_timestamp: now - OFFLINE_THRESHOLD_SECS / 2,
    };

    assert.deepEqual(status_from_raw(raw, alice), {
        status: "active",
        last_active: raw.active_timestamp,
    });

    raw = {
        server_timestamp: now,
        active_timestamp: now - OFFLINE_THRESHOLD_SECS * 2,
    };

    assert.deepEqual(status_from_raw(raw, alice), {
        status: "offline",
        last_active: raw.active_timestamp,
    });

    raw = {
        server_timestamp: now,
        idle_timestamp: now - OFFLINE_THRESHOLD_SECS / 2,
    };

    assert.deepEqual(status_from_raw(raw, alice), {
        status: "idle",
        last_active: raw.idle_timestamp,
    });

    const user = people.get_by_user_id(alice.user_id);
    user.date_joined = new Date((now - OFFLINE_THRESHOLD_SECS * 200) * 1000);

    raw = {
        server_timestamp: now,
        active_timestamp: now - OFFLINE_THRESHOLD_SECS * 200,
        idle_timestamp: now - OFFLINE_THRESHOLD_SECS * 100,
    };
    assert.deepEqual(status_from_raw(raw, alice), {
        status: "offline",
        last_active: raw.active_timestamp,
    });
});

test("set_presence_info", () => {
    const presences = {};
    const now = 5000;
    const recent = now + 1 - OFFLINE_THRESHOLD_SECS;
    const a_while_ago = now - OFFLINE_THRESHOLD_SECS * 2;

    const unknown_user_id = 999;

    presences[alice.user_id.toString()] = {
        active_timestamp: recent,
    };

    presences[fred.user_id.toString()] = {
        active_timestamp: a_while_ago,
        idle_timestamp: now,
    };

    presences[me.user_id.toString()] = {
        active_timestamp: now,
    };

    presences[sally.user_id.toString()] = {
        active_timestamp: a_while_ago,
    };

    presences[john.user_id.toString()] = {
        idle_timestamp: a_while_ago,
    };

    presences[jane.user_id.toString()] = {
        idle_timestamp: now,
    };

    // Unknown user ids can also be in the presence data.
    presences[unknown_user_id.toString()] = {
        idle_timestamp: now,
    };

    presences[inaccessible_user_id.toString()] = {
        idle_timestamp: now,
    };

    const params = {};
    params.presences = presences;
    params.server_timestamp = now;
    presence.initialize(params);

    assert.deepEqual(presence.presence_info.get(alice.user_id), {
        status: "active",
        last_active: recent,
    });
    assert.equal(presence.get_status(alice.user_id), "active");
    assert.deepEqual(presence.last_active_date(alice.user_id), new Date(recent * 1000));

    assert.deepEqual(presence.presence_info.get(fred.user_id), {status: "idle", last_active: now});
    assert.equal(presence.get_status(fred.user_id), "idle");

    assert.deepEqual(presence.presence_info.get(me.user_id), {status: "active", last_active: now});
    assert.equal(presence.get_status(me.user_id), "active");

    assert.deepEqual(presence.presence_info.get(sally.user_id), {
        status: "offline",
        last_active: a_while_ago,
    });
    assert.equal(presence.get_status(sally.user_id), "offline");

    assert.deepEqual(presence.presence_info.get(zoe.user_id), {
        status: "offline",
        last_active: undefined,
    });
    assert.equal(presence.get_status(zoe.user_id), "offline");
    assert.equal(presence.last_active_date(zoe.user_id), undefined);

    assert.ok(!presence.presence_info.has(bot.user_id));
    assert.equal(presence.get_status(bot.user_id), "offline");

    assert.deepEqual(presence.presence_info.get(john.user_id), {
        status: "offline",
        // Fall back to date_joined, which we set to 75 seconds after the epoch above.
        last_active: 75,
    });
    assert.equal(presence.get_status(john.user_id), "offline");

    assert.deepEqual(presence.presence_info.get(jane.user_id), {status: "idle", last_active: now});
    assert.equal(presence.get_status(jane.user_id), "idle");

    assert.deepEqual(presence.presence_info.get(unknown_user_id), {
        status: "idle",
        last_active: now,
    });
    assert.equal(presence.get_status(unknown_user_id), "idle");

    assert.equal(presence.presence_info.get(inaccessible_user_id), undefined);
});

test("missing values", () => {
    /*
        When a user does not have a relevant active timestamp,
        the server just leaves off the `active_timestamp` field
        to save bandwidth, which looks like `undefined` to us
        if we try to dereference it.
    */
    const now = 2000000;
    const a_bit_ago = now - 5;
    const presences = {};

    presences[zoe.user_id.toString()] = {
        idle_timestamp: a_bit_ago,
    };

    presence.set_info(presences, now);

    assert.deepEqual(presence.presence_info.get(zoe.user_id), {
        status: "idle",
        last_active: a_bit_ago,
    });

    presences[zoe.user_id.toString()] = {};

    presence.set_info(presences, now);

    assert.deepEqual(presence.presence_info.get(zoe.user_id), {
        status: "offline",
        // This shouldn't happen in reality, but covers not crashing
        // if we don't have a last_active_time.
        last_active: 0,
    });
});

test("big realms", ({override_rewire}) => {
    const presences = {};
    const now = 5000;

    presences[sally.user_id.toString()] = {
        active_timestamp: now,
    };

    // Make it seem like realm has a lot of people, in
    // which case we will not provide default values for
    // users that aren't in our presences payload.
    override_rewire(people, "get_active_human_count", () => 1000);
    presence.set_info(presences, now);
    assert.ok(presence.presence_info.has(sally.user_id));
    assert.ok(!presence.presence_info.has(zoe.user_id));
});

test("last_active_date", () => {
    const unknown_id = 42;
    presence.presence_info.clear();
    presence.presence_info.set(alice.user_id, {last_active: 500});
    presence.presence_info.set(fred.user_id, {});

    assert.equal(presence.last_active_date(unknown_id), undefined);
    assert.equal(presence.last_active_date(fred.user_id), undefined);
    assert.deepEqual(presence.last_active_date(alice.user_id), new Date(500 * 1000));
});

test("update_info_from_event", () => {
    let info;

    info = {
        website: {
            status: "active",
            timestamp: 500,
        },
    };

    presence.presence_info.delete(alice.user_id);
    presence.update_info_from_event(alice.user_id, info, 500);

    assert.deepEqual(presence.presence_info.get(alice.user_id), {
        status: "active",
        last_active: 500,
    });

    info = {
        mobile: {
            status: "idle",
            timestamp: 510,
        },
    };
    presence.update_info_from_event(alice.user_id, info, 510);

    assert.deepEqual(presence.presence_info.get(alice.user_id), {
        status: "active",
        last_active: 500,
    });

    info = {
        mobile: {
            status: "idle",
            timestamp: 1000,
        },
    };
    presence.update_info_from_event(alice.user_id, info, 1000);

    assert.deepEqual(presence.presence_info.get(alice.user_id), {
        status: "idle",
        last_active: 1000,
    });
});
