// This module just manages data.  See activity.js for
// the UI of our buddy list.

// Dictionary mapping user_id -> presence data.  May contain user_id
// values that are not yet registered in people.js (see long comment
// in `set_info` below for details).
exports.presence_info = new Map();


/* Mark users as offline after 140 seconds since their last checkin,
 * Keep in sync with zerver/tornado/event_queue.py:receiver_is_idle
 */
const OFFLINE_THRESHOLD_SECS = 140;

const BIG_REALM_COUNT = 250;

exports.is_active = function (user_id) {
    if (exports.presence_info.has(user_id)) {
        const status = exports.presence_info.get(user_id).status;
        if (status && status === "active") {
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

function status_from_timestamp(baseline_time, info) {
    let status = 'offline';
    let last_active = 0;

    for (const [device, device_presence] of Object.entries(info)) {
        const age = baseline_time - device_presence.timestamp;
        if (last_active < device_presence.timestamp) {
            last_active = device_presence.timestamp;
        }
        if (age < OFFLINE_THRESHOLD_SECS) {
            switch (device_presence.status) {
            case 'active':
                status = device_presence.status;
                break;
            case 'idle':
                if (status !== 'active') {
                    status = device_presence.status;
                }
                break;
            case 'offline':
                if (status !== 'active' && status !== 'idle') {
                    status = device_presence.status;
                }
                break;
            default:
                blueslip.error('Unexpected status', {presence_object: device_presence, device: device}, undefined);
            }
        }
    }
    return {status: status,
            last_active: last_active };
}

// For testing
exports._status_from_timestamp = status_from_timestamp;

exports.set_info_for_user = function (user_id, info, server_time) {
    const status = status_from_timestamp(server_time, info);
    exports.presence_info.set(user_id, status);
};

exports.set_info = function (presences, server_timestamp) {
    exports.presence_info.clear();
    for (const [user_id_str, info] of Object.entries(presences)) {
        // Note: In contrast with essentially every other piece of
        // state updates we receive from the server, precense updates
        // are pulled independently from server_events_dispatch.js.
        //
        // This means that if we're coming back from offline and new
        // users were created in the meantime, we'll be populating
        // exports.presence_info with user IDs not yet present in
        // people.js.  This is safe because we always access
        // exports.presence_info as a filter on sets of users obtained
        // elsewhere, but we need to be careful to avoid trying to
        // look up user_ids obtained via presence_info in other data
        // sources.
        const status = status_from_timestamp(server_timestamp,
                                             info);

        const user_id = parseInt(user_id_str, 10);
        exports.presence_info.set(user_id, status);
    }
    exports.update_info_for_small_realm();
};

exports.update_info_for_small_realm = function () {
    if (people.get_realm_count() >= BIG_REALM_COUNT) {
        // For big realms, we don't want to bloat our buddy
        // lists with lots of long-time-inactive users.
        return;
    }

    // For small realms, we create presence info for users
    // that the server didn't include in its presence update.
    const persons = people.get_realm_persons();

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
            status: status,
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

window.presence = exports;
