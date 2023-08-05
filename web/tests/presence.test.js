"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const {page_params, user_settings} = require("./lib/zpage_params");

const reload_state = mock_esm("../src/reload_state", {
    is_in_progress: () => false,
});

const people = zrequire("people");
const watchdog = zrequire("watchdog");
const presence = zrequire("presence");

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
people.initialize_current_user(me.user_id);

function test(label, f) {
    run_test(label, (helpers) => {
        page_params.server_presence_offline_threshold_seconds = OFFLINE_THRESHOLD_SECS;
        user_settings.presence_enabled = true;
        presence.clear_internal_data();
        f(helpers);
    });
}

test("my user", () => {
    assert.equal(presence.get_status(me.user_id), "active");
});

test("unknown user", ({override}) => {
    const unknown_user_id = 999;
    const now = 888888;
    const presences = {};
    presences[unknown_user_id.toString()] = "does-not-matter";

    blueslip.expect("error", "Unknown user ID in presence data");
    presence.set_info(presences, now);

    // If the server is suspected to be offline or reloading,
    // then we suppress errors.  The use case here is that we
    // haven't gotten info for a brand new user yet.
    watchdog.set_suspect_offline(true);
    presence.set_info(presences, now);

    watchdog.set_suspect_offline(false);
    override(reload_state, "is_in_progress", () => true);
    presence.set_info(presences, now);
});

test("status_from_raw", () => {
    const status_from_raw = presence.status_from_raw;

    const now = 5000;
    let raw;

    raw = {
        server_timestamp: now,
        active_timestamp: now - OFFLINE_THRESHOLD_SECS / 2,
    };

    assert.deepEqual(status_from_raw(raw), {
        status: "active",
        last_active: raw.active_timestamp,
    });

    raw = {
        server_timestamp: now,
        active_timestamp: now - OFFLINE_THRESHOLD_SECS * 2,
    };

    assert.deepEqual(status_from_raw(raw), {
        status: "offline",
        last_active: raw.active_timestamp,
    });

    raw = {
        server_timestamp: now,
        idle_timestamp: now - OFFLINE_THRESHOLD_SECS / 2,
    };

    assert.deepEqual(status_from_raw(raw), {
        status: "idle",
        last_active: raw.idle_timestamp,
    });
});

test("set_presence_info", () => {
    const presences = {};
    const now = 5000;
    const recent = now + 1 - OFFLINE_THRESHOLD_SECS;
    const a_while_ago = now - OFFLINE_THRESHOLD_SECS * 2;

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
        last_active: a_while_ago,
    });
    assert.equal(presence.get_status(john.user_id), "offline");

    assert.deepEqual(presence.presence_info.get(jane.user_id), {status: "idle", last_active: now});
    assert.equal(presence.get_status(jane.user_id), "idle");
});

test("falsy values", () => {
    /*
        When a user does not have a relevant active timestamp,
        the server just leaves off the `active_timestamp` field
        to save bandwidth, which looks like `undefined` to us
        if we try to dereference it.

        Our code should just treat all falsy values the same way,
        though, to defend against bugs where we say the person
        was last online in 1970 or silly things like that.
    */
    const now = 2000000;
    const a_bit_ago = now - 5;
    const presences = {};

    for (const falsy_value of [undefined, 0, null]) {
        presences[zoe.user_id.toString()] = {
            active_timestamp: falsy_value,
            idle_timestamp: a_bit_ago,
        };

        presence.set_info(presences, now);

        assert.deepEqual(presence.presence_info.get(zoe.user_id), {
            status: "idle",
            last_active: a_bit_ago,
        });

        presences[zoe.user_id.toString()] = {
            active_timestamp: falsy_value,
            idle_timestamp: falsy_value,
        };

        presence.set_info(presences, now);

        assert.deepEqual(presence.presence_info.get(zoe.user_id), {
            status: "offline",
            last_active: undefined,
        });
    }
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
        last_active: 510,
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
