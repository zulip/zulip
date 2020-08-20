"use strict";

const XDate = require("xdate");

const people = require("./people");

// This module just manages data.  See activity.js for
// the UI of our buddy list.

// The following Maps have user_id as the key.  Some of the
// user_ids may not yet be registered in people.js.
// See the long comment in `set_info` below for details.

// In future commits we'll use raw_info to facilitate
// handling server events and/or timeout events.
const raw_info = new Map();
exports.presence_info = new Map();

/* Mark users as offline after 140 seconds since their last checkin,
 * Keep in sync with zerver/tornado/event_queue.py:receiver_is_idle
 */
const OFFLINE_THRESHOLD_SECS = 140;

const BIG_REALM_COUNT = 250;

exports.is_active = function (user_id) {
    if (exports.presence_info.has(user_id)) {
        const status = exports.presence_info.get(user_id).status;
        if (status === "active") {
            return true;
        }
    }
    return false;
};

exports.get_status = function (user_id) {
    if (people.is_my_user_id(user_id)) {
        return "active";
    }
    if (exports.presence_info.has(user_id)) {
        return exports.presence_info.get(user_id).status;
    }
    return "offline";
};

exports.get_user_ids = function () {
    return Array.from(exports.presence_info.keys());
};

exports.status_from_raw = function (raw) {
    /*
        Example of `raw`:

        {
            active_timestamp: 1585745133
            idle_timestamp: 1585745091
            server_timestamp: 1585745140
        }
    */
    function age(timestamp) {
        return raw.server_timestamp - (timestamp || 0);
    }

    const active_timestamp = raw.active_timestamp;
    const idle_timestamp = raw.idle_timestamp;

    let last_active;
    if (active_timestamp !== undefined || idle_timestamp !== undefined) {
        last_active = Math.max(active_timestamp || 0, idle_timestamp || 0);
    }

    /*
        If the server sends us `active_timestamp`, this
        means at least one client was active at this time
        (and hasn't changed since).

        As long as the timestamp is current enough, we will
        show the user as active (even if there's a newer
        timestamp for idle).
    */
    if (age(active_timestamp) < OFFLINE_THRESHOLD_SECS) {
        return {
            status: "active",
            last_active,
        };
    }

    if (age(idle_timestamp) < OFFLINE_THRESHOLD_SECS) {
        return {
            status: "idle",
            last_active,
        };
    }

    return {
        status: "offline",
        last_active,
    };
};

exports.update_info_from_event = function (user_id, info, server_timestamp) {
    /*
        Example of `info`:

        {
            website: {
                client: 'website',
                pushable: false,
                status: 'active',
                timestamp: 1585745225
            }
        }

        Example of `raw`:

        {
            active_timestamp: 1585745133
            idle_timestamp: 1585745091
            server_timestamp: 1585745140
        }
    */
    const raw = raw_info.get(user_id) || {};

    raw.server_timestamp = server_timestamp;

    for (const rec of Object.values(info)) {
        if (rec.status === "active") {
            if (rec.timestamp > (raw.active_timestamp || 0)) {
                raw.active_timestamp = rec.timestamp;
            }
        }

        if (rec.status === "idle") {
            if (rec.timestamp > (raw.idle_timestamp || 0)) {
                raw.idle_timestamp = rec.timestamp;
            }
        }
    }

    raw_info.set(user_id, raw);

    const status = exports.status_from_raw(raw);
    exports.presence_info.set(user_id, status);
};

exports.set_info = function (presences, server_timestamp) {
    /*
        Example `presences` data:

        {
            6: Object { idle_timestamp: 1585746028 },
            7: Object { active_timestamp: 1585745774 },
            8: Object { active_timestamp: 1585745578 }
        }
    */

    raw_info.clear();
    exports.presence_info.clear();
    for (const [user_id_str, info] of Object.entries(presences)) {
        const user_id = parseInt(user_id_str, 10);

        // Note: In contrast with all other state updates received
        // receive from the server, presence data is updated via a
        // polling process rather than the events system
        // (server_events_dispatch.js).
        //
        // This means that if we're coming back from being offline and
        // new users were created in the meantime, we may see user IDs
        // not yet present in people.js if server_events doesn't have
        // current data (or we've been offline, our event queue was
        // GC'ed, and we're about to reload).  Such user_ids being
        // present could, in turn, create spammy downstream exceptions
        // when rendering the buddy list.  To address this, we check
        // if the user ID is not yet present in people.js, and if it
        // is, we skip storing that user (we'll see them again in the
        // next presence request in 1 minute anyway).
        //
        // It's important to check both suspect_offline and
        // reload_state.is_in_progress, because races where presence
        // returns data on users not yet received via the server_events
        // system are common in both situations.
        const person = people.get_by_user_id(user_id, true);
        if (person === undefined) {
            if (!(server_events.suspect_offline || reload_state.is_in_progress())) {
                // If we're online, and we get a user who we don't
                // know about in the presence data, throw an error.
                blueslip.error("Unknown user ID in presence data: " + user_id);
            }
            // Either way, we deal by skipping this user and
            // continuing with processing everyone else.
            continue;
        }

        const raw = {
            server_timestamp,
            active_timestamp: info.active_timestamp || undefined,
            idle_timestamp: info.idle_timestamp || undefined,
        };

        raw_info.set(user_id, raw);

        const status = exports.status_from_raw(raw);
        exports.presence_info.set(user_id, status);
    }
    exports.update_info_for_small_realm();
};

exports.update_info_for_small_realm = function () {
    if (people.get_active_human_count() >= BIG_REALM_COUNT) {
        // For big realms, we don't want to bloat our buddy
        // lists with lots of long-time-inactive users.
        return;
    }

    // For small realms, we create presence info for users
    // that the server didn't include in its presence update.
    const persons = people.get_realm_users();

    for (const person of persons) {
        const user_id = person.user_id;
        let status = "offline";

        if (exports.presence_info.has(user_id)) {
            // this is normal, we have data for active
            // users that we don't want to clobber.
            continue;
        }

        if (person.is_bot) {
            // we don't show presence for bots
            continue;
        }

        if (people.is_my_user_id(user_id)) {
            status = "active";
        }

        exports.presence_info.set(user_id, {
            status,
            last_active: undefined,
        });
    }
};

exports.last_active_date = function (user_id) {
    const info = exports.presence_info.get(user_id);

    if (!info || !info.last_active) {
        return;
    }

    const date = new XDate(info.last_active * 1000);
    return date;
};

exports.initialize = function (params) {
    exports.set_info(params.presences, params.initial_servertime);
};

window.presence = exports;
