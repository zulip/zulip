import * as blueslip from "./blueslip";
import {page_params} from "./page_params";
import * as people from "./people";
import * as reload_state from "./reload_state";
import {user_settings} from "./user_settings";
import * as watchdog from "./watchdog";

// This module just manages data.  See activity.js for
// the UI of our buddy list.

// The following Maps have user_id as the key.  Some of the
// user_ids may not yet be registered in people.js.
// See the long comment in `set_info` below for details.

// In future commits we'll use raw_info to facilitate
// handling server events and/or timeout events.
const raw_info = new Map();
export const presence_info = new Map();

// We use this internally and export it for testing convenience.
export function clear_internal_data() {
    raw_info.clear();
    presence_info.clear();
}

const BIG_REALM_COUNT = 250;

export function get_status(user_id) {
    if (people.is_my_user_id(user_id)) {
        if (user_settings.presence_enabled) {
            // if the current user is sharing presence, they always see themselves as online.
            return "active";
        }
        // if the current user is not sharing presence, they always see themselves as offline.
        return "offline";
    }
    if (presence_info.has(user_id)) {
        return presence_info.get(user_id).status;
    }
    return "offline";
}

export function get_user_ids() {
    return [...presence_info.keys()];
}

export function status_from_raw(raw) {
    /*
        Example of `raw`:

        {
            active_timestamp: 1585745133
            idle_timestamp: 1585745091
            server_timestamp: 1585745140
        }
    */

    /* Mark users as offline after this many seconds since their last checkin, */
    const offline_threshold_secs = page_params.server_presence_offline_threshold_seconds;

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
    if (age(active_timestamp) < offline_threshold_secs) {
        return {
            status: "active",
            last_active,
        };
    }

    if (age(idle_timestamp) < offline_threshold_secs) {
        return {
            status: "idle",
            last_active,
        };
    }

    return {
        status: "offline",
        last_active,
    };
}

export function update_info_from_event(user_id, info, server_timestamp) {
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
        if (rec.status === "active" && rec.timestamp > (raw.active_timestamp || 0)) {
            raw.active_timestamp = rec.timestamp;
        }

        if (rec.status === "idle" && rec.timestamp > (raw.idle_timestamp || 0)) {
            raw.idle_timestamp = rec.timestamp;
        }
    }

    raw_info.set(user_id, raw);

    const status = status_from_raw(raw);
    presence_info.set(user_id, status);
}

export function set_info(presences, server_timestamp) {
    /*
        Example `presences` data:

        {
            6: Object { idle_timestamp: 1585746028 },
            7: Object { active_timestamp: 1585745774 },
            8: Object { active_timestamp: 1585745578 }
        }
    */

    clear_internal_data();
    for (const [user_id_str, info] of Object.entries(presences)) {
        const user_id = Number.parseInt(user_id_str, 10);

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
        const person = people.maybe_get_user_by_id(user_id, true);
        if (person === undefined) {
            if (!(watchdog.suspects_user_is_offline() || reload_state.is_in_progress())) {
                // If we're online, and we get a user who we don't
                // know about in the presence data, throw an error.
                blueslip.error("Unknown user ID in presence data", {user_id});
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

        const status = status_from_raw(raw);
        presence_info.set(user_id, status);
    }
    update_info_for_small_realm();
}

export function update_info_for_small_realm() {
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

        if (presence_info.has(user_id)) {
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

        presence_info.set(user_id, {
            status,
            last_active: undefined,
        });
    }
}

export function last_active_date(user_id) {
    const info = presence_info.get(user_id);

    if (!info || !info.last_active) {
        return undefined;
    }

    return new Date(info.last_active * 1000);
}

export function initialize(params) {
    set_info(params.presences, params.server_timestamp);
}
