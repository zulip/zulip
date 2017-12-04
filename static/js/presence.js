var presence = (function () {
var exports = {};

// This module just manages data.  See activity.js for
// the UI of our buddy list.

exports.presence_info = {};


/* Mark users as offline after 140 seconds since their last checkin,
 * Keep in sync with zerver/tornado/event_queue.py:receiver_is_idle
 */
var OFFLINE_THRESHOLD_SECS = 140;

var BIG_REALM_COUNT = 250;

var MOBILE_DEVICES = ["Android", "ZulipiOS", "ios"];

function is_mobile(device) {
    return MOBILE_DEVICES.indexOf(device) !== -1;
}

exports.is_not_offline = function (user_id) {
    var presence_info = exports.presence_info;

    if (presence_info[user_id]) {
        var status = presence_info[user_id].status;
        if (status && (status !== 'offline')) {
            return true;
        }
    }
    return false;
};

exports.get_status = function (user_id) {
    if (user_id === page_params.user_id) {
        return "active";
    }
    if (user_id in exports.presence_info) {
        return exports.presence_info[user_id].status;
    }
    return "offline";
};

exports.get_user_ids = function () {
    var user_ids = Object.keys(exports.presence_info);
    return user_ids;
};

function status_from_timestamp(baseline_time, info) {
    var status = 'offline';
    var last_active = 0;
    var mobileAvailable = false;
    var nonmobileAvailable = false;
    _.each(info, function (device_presence, device) {
        var age = baseline_time - device_presence.timestamp;
        if (last_active < device_presence.timestamp) {
            last_active = device_presence.timestamp;
        }
        if (is_mobile(device)) {
            mobileAvailable = device_presence.pushable || mobileAvailable;
        }
        if (age < OFFLINE_THRESHOLD_SECS) {
            switch (device_presence.status) {
                case 'active':
                    if (is_mobile(device)) {
                        mobileAvailable = true;
                    } else {
                        nonmobileAvailable = true;
                    }
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
    });
    return {status: status,
            mobile: !nonmobileAvailable && mobileAvailable,
            last_active: last_active };
}

// For testing
exports._status_from_timestamp = status_from_timestamp;

exports.set_user_status = function (user_id, info, server_time) {
    var status = status_from_timestamp(server_time, info);
    exports.presence_info[user_id] = status;
};

exports.set_info = function (presences, server_timestamp) {
    exports.presence_info = {};
    _.each(presences, function (info, this_email) {
        if (!people.is_current_user(this_email)) {
            var person = people.get_by_email(this_email);
            if (person === undefined) {
                if (!server_events.suspect_offline) {
                    // If we're online, and we get a user who we don't
                    // know about in the presence data, throw an error.
                    blueslip.error('Unknown email in presence data: ' + this_email);
                }
                // Either way, we deal by skipping this user and
                // rendering everyone else, to avoid disruption.
                return;
            }
            var user_id = person.user_id;
            if (user_id) {
                var status = status_from_timestamp(server_timestamp,
                                                   info);
                exports.presence_info[user_id] = status;
            }
        }
    });
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
    var presence_info = exports.presence_info;
    var persons = people.get_realm_persons();

    _.each(persons, function (person) {
        var user_id = person.user_id;

        if (people.is_my_user_id(user_id)) {
            return;
        }

        if (presence_info[user_id]) {
            // this is normal, we have data for active
            // users that we don't want to clobber.
            return;
        }

        if (person.is_bot) {
            // we don't show presence for bots
            return;
        }

        presence_info[user_id] = {
            status: "offline",
            mobile: false,
            last_active: undefined,
        };
    });
};

exports.last_active_date = function (user_id) {
    var info = exports.presence_info[user_id];

    if (!info || !info.last_active) {
        return;
    }

    var date = new XDate(info.last_active * 1000);
    return date;
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = presence;
}
