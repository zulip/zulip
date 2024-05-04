import * as people from "./people";
import {realm} from "./state_data";
import {user_settings} from "./user_settings";

export type RawPresence = {
    server_timestamp: number;
    active_timestamp?: number;
    idle_timestamp?: number;
};

export type PresenceStatus = {
    status: "active" | "idle" | "offline";
    last_active?: number;
};

export type PresenceInfoFromEvent = {
    website: {
        client: "website";
        status: "idle" | "active";
        timestamp: number;
        pushable: boolean;
    };
};

// This module just manages data.  See activity.js for
// the UI of our buddy list.

// The following Maps have user_id as the key.  Some of the
// user_ids may not yet be registered in people.js.
// See the long comment in `set_info` below for details.

// In future commits we'll use raw_info to facilitate
// handling server events and/or timeout events.
const raw_info = new Map<number, RawPresence>();
export const presence_info = new Map<number, PresenceStatus>();

// We use this internally and export it for testing convenience.
export function clear_internal_data(): void {
    raw_info.clear();
    presence_info.clear();
}

const BIG_REALM_COUNT = 250;

export function get_status(user_id: number): PresenceStatus["status"] {
    if (people.is_my_user_id(user_id)) {
        if (user_settings.presence_enabled) {
            // if the current user is sharing presence, they always see themselves as online.
            return "active";
        }
        // if the current user is not sharing presence, they always see themselves as offline.
        return "offline";
    }
    if (presence_info.has(user_id)) {
        return presence_info.get(user_id)!.status;
    }
    return "offline";
}

export function get_user_ids(): number[] {
    return [...presence_info.keys()];
}

export function status_from_raw(raw: RawPresence): PresenceStatus {
    /*
        Example of `raw`:

        {
            active_timestamp: 1585745133
            idle_timestamp: 1585745091
            server_timestamp: 1585745140
        }
    */

    /* Mark users as offline after this many seconds since their last checkin, */
    const offline_threshold_secs = realm.server_presence_offline_threshold_seconds;

    function age(timestamp = 0): number {
        return raw.server_timestamp - timestamp;
    }

    const active_timestamp = raw.active_timestamp;
    const idle_timestamp = raw.idle_timestamp;

    let last_active: number | undefined;
    if (active_timestamp !== undefined || idle_timestamp !== undefined) {
        last_active = Math.max(active_timestamp ?? 0, idle_timestamp ?? 0);
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

export function update_info_from_event(
    user_id: number,
    info: PresenceInfoFromEvent,
    server_timestamp: number,
): void {
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
    const raw = raw_info.get(user_id) ?? {
        server_timestamp: 0,
    };

    raw.server_timestamp = server_timestamp;

    for (const rec of Object.values(info)) {
        if (rec.status === "active" && rec.timestamp > (raw.active_timestamp ?? 0)) {
            raw.active_timestamp = rec.timestamp;
        }

        if (rec.status === "idle" && rec.timestamp > (raw.idle_timestamp ?? 0)) {
            raw.idle_timestamp = rec.timestamp;
        }
    }

    raw_info.set(user_id, raw);

    const status = status_from_raw(raw);
    presence_info.set(user_id, status);
}

export function set_info(
    presences: Record<number, Omit<RawPresence, "server_timestamp">>,
    server_timestamp: number,
): void {
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
        // from the server, presence data is updated via a
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
        if (person === undefined || person.is_inaccessible_user) {
            // There are a number of situations where it is expected
            // that we get presence data for a user ID that we do
            // not have in our user database, including when we're
            // offline/reloading (watchdog.suspects_user_is_offline()
            // || reload_state.is_in_progress()), when
            // CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE is disabled,
            // and whenever presence wins a race with the events system
            // for events regarding a newly created or visible user.
            //
            // Either way, we deal by skipping this user and
            // continuing with processing everyone else.
            continue;
        }

        const raw: RawPresence = {
            server_timestamp,
            active_timestamp: info.active_timestamp,
            idle_timestamp: info.idle_timestamp,
        };

        raw_info.set(user_id, raw);

        const status = status_from_raw(raw);
        presence_info.set(user_id, status);
    }
    update_info_for_small_realm();
}

export function update_info_for_small_realm(): void {
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
        let status: PresenceStatus["status"] = "offline";

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

export function last_active_date(user_id: number): Date | undefined {
    const info = presence_info.get(user_id);

    if (!info?.last_active) {
        return undefined;
    }

    return new Date(info.last_active * 1000);
}

export function initialize(params: {
    presences: Record<number, Omit<RawPresence, "server_timestamp">>;
    server_timestamp: number;
}): void {
    set_info(params.presences, params.server_timestamp);
}
