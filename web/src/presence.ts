import * as z from "zod/mini";

import * as people from "./people.ts";
import type {User} from "./people.ts";
import type {StateData, presence_schema} from "./state_data.ts";
import {realm} from "./state_data.ts";
import {user_settings} from "./user_settings.ts";

export type RawPresence = z.infer<typeof presence_schema> & {
    server_timestamp: number;
};

export type PresenceStatus = {
    status: "active" | "idle" | "offline";
    last_active?: number | undefined;
};

export const presence_info_from_event_schema = z.object({
    website: z.object({
        client: z.literal("website"),
        status: z.enum(["idle", "active"]),
        timestamp: z.number(),
        pushable: z.boolean(),
    }),
});
export type PresenceInfoFromEvent = z.output<typeof presence_info_from_event_schema>;

export const user_last_seen_response_schema = z.object({
    result: z.string(),
    msg: z.optional(z.string()),
    presence: z.optional(
        z.object({
            /* We ignore the keys other than aggregated, since they just contain
               duplicate data. */
            aggregated: z.object({
                status: z.enum(["active", "idle", "offline"]),
                timestamp: z.number(),
            }),
        }),
    ),
});

// This module just manages data.  See activity.js for
// the UI of our buddy list.

// The following Maps have user_id as the key.  Some of the
// user_ids may not yet be registered in people.js.
// See the long comment in `set_info` below for details.

// In future commits we'll use raw_info to facilitate
// handling server events and/or timeout events.
const raw_info = new Map<number, RawPresence>();
export const presence_info = new Map<number, PresenceStatus>();

// An integer that is updated whenever we get new presence data.
// TODO: Improve this comment.
export let presence_last_update_id = -1;

// We keep and export this for testing convenience.
export function clear_internal_data(): void {
    raw_info.clear();
    presence_info.clear();

    presence_last_update_id = -1;
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

export function get_active_or_idle_user_ids(): number[] {
    return [...presence_info.entries()]
        .filter((entry) => entry[1].status !== "offline")
        .map((entry) => entry[0]);
}

export function status_from_raw(raw: RawPresence, user: User | undefined): PresenceStatus {
    /*
        Example of `raw`:

        {
            active_timestamp: 1585745133
            idle_timestamp: 1585745091
            server_timestamp: 1585745140
        }
    */

    /* Mark users as offline after this many seconds since their last check-in, */
    const offline_threshold_secs = realm.server_presence_offline_threshold_seconds;

    function age(timestamp = 0): number {
        return raw.server_timestamp - timestamp;
    }

    const active_timestamp = raw.active_timestamp;
    const idle_timestamp = raw.idle_timestamp;

    let last_active: number | undefined;

    /*
        If the server sends us `active_timestamp`, this
        means at least one client was active at this time
        (and hasn't changed since).

        As long as the timestamp is current enough, we will
        show the user as active (even if there's a newer
        timestamp for idle).
    */
    if (age(active_timestamp) < offline_threshold_secs) {
        last_active = active_timestamp;
        return {
            status: "active",
            last_active,
        };
    }

    if (age(idle_timestamp) < offline_threshold_secs) {
        // idle_timestamp >= active_timestamp usually, but it's
        // harmless to just take the maximum for readability.
        last_active = Math.max(active_timestamp ?? 0, idle_timestamp ?? 0);
        return {
            status: "idle",
            last_active,
        };
    }

    /*
        We always want to prioritize the last time the user was active
        'active_timestamp' to be displayed in the popover. This since
        it is the most relevant information for other users and
        matches the formatting of the string in the popover. For users
        who've never logged in, we fall back to when they joined.
    */

    let date_joined_timestamp = 0;
    if (user?.date_joined) {
        date_joined_timestamp = new Date(user.date_joined).getTime() / 1000;
    }
    last_active = Math.max(active_timestamp ?? 0, date_joined_timestamp);

    return {
        status: "offline",
        last_active,
    };
}

export function update_info_from_event(
    user_id: number,
    info: PresenceInfoFromEvent | null,
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

    for (const rec of Object.values(info ?? {})) {
        if (rec.status === "active" && rec.timestamp > (raw.active_timestamp ?? 0)) {
            raw.active_timestamp = rec.timestamp;
        }

        if (rec.status === "idle" && rec.timestamp > (raw.idle_timestamp ?? 0)) {
            raw.idle_timestamp = rec.timestamp;
        }
    }

    raw_info.set(user_id, raw);

    const ignore_missing = true;
    const user = people.maybe_get_user_by_id(user_id, ignore_missing);
    const status = status_from_raw(raw, user);
    presence_info.set(user_id, status);
}

export function set_info(
    presences: Record<number, z.infer<typeof presence_schema>>,
    server_timestamp: number,
    last_update_id = -1,
): void {
    /*
        Example `presences` data:

        {
            6: Object { idle_timestamp: 1585746028 },
            7: Object { active_timestamp: 1585745774 },
            8: Object { active_timestamp: 1585745578 }
        }
    */

    presence_last_update_id = last_update_id;
    const all_active_or_idle_user_ids = new Set(get_active_or_idle_user_ids());

    for (const [user_id_str, info] of Object.entries(presences)) {
        const user_id = Number.parseInt(user_id_str, 10);
        // Remove the user from all_active_or_idle_user_ids since we already
        // updated their presence info.
        all_active_or_idle_user_ids.delete(user_id);

        // Note: In contrast with all other state updates received
        // from the server, presence data is updated via a
        // polling process rather than the events system
        // (server_events_dispatch.js).
        //
        // This means that if we're coming back from being offline and
        // new users were created in the meantime, we may see user IDs
        // not yet present in people.js if server_events doesn't have
        // current data (or we've been offline, our event queue was
        // GC'ed, and we're about to reload).
        // Despite that, we still add the presence data to our structures,
        // and it is the job of the code using them to correctly
        // ignore these until we receive the basic metadata on this user.
        // We skip inaccessible users here, as we do in other places;
        // presence info for them is not used.
        const person = people.maybe_get_user_by_id(user_id, true);
        if (person?.is_inaccessible_user) {
            // There are a number of situations where it is expected
            // that we get presence data for a user ID that we do
            // not have in our user database, including when we're
            // offline/reloading (watchdog.suspects_user_is_offline()
            // || reload_state.is_in_progress()), when
            // CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE is disabled,
            // and whenever presence wins a race with the events system
            // for events regarding a newly created or visible user.
            //
            // Either way, we still record the information unless
            // we're dealing with an inaccessible user.
            continue;
        }

        const raw: RawPresence = {
            server_timestamp,
            active_timestamp: info.active_timestamp,
            idle_timestamp: info.idle_timestamp,
        };

        raw_info.set(user_id, raw);

        const status = status_from_raw(raw, person);
        presence_info.set(user_id, status);
    }
    for (const user_id of all_active_or_idle_user_ids) {
        update_info_from_event(user_id, null, server_timestamp);
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

export function initialize(params: StateData["presence"]): void {
    set_info(params.presences, params.server_timestamp, params.presence_last_update_id);
}
