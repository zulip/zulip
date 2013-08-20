var activity = (function () {
var exports = {};

/*
    Helpers for detecting user activity and managing user idle states
*/

/* Broadcast "idle" to server after 5 minutes of local inactivity */
var DEFAULT_IDLE_TIMEOUT_MS = 5 * 60 * 1000;
/* Time between keep-alive pings */
var ACTIVE_PING_INTERVAL_MS = 60 * 1000;

/* Mark users as offline after 70 seconds since their last checkin */
var OFFLINE_THRESHOLD_SECS = 70;

/* Keep in sync with views.py:json_update_active_status() */
exports.ACTIVE = "active";
exports.IDLE = "idle";

exports.has_focus = true;

var user_info = {};

function sort_users(users, user_info) {
    // TODO sort by unread count first, once we support that
    users.sort(function (a, b) {
        if (user_info[a] === 'active' && user_info[b] !== 'active') {
            return -1;
        } else if (user_info[b] === 'active' && user_info[a] !== 'active') {
            return 1;
        }

        if (user_info[a] === 'idle' && user_info[b] !== 'idle') {
            return -1;
        } else if (user_info[b] === 'idle' && user_info[a] !== 'idle') {
            return 1;
        }

        // Sort equivalent PM names alphabetically
        var full_name_a = a;
        var full_name_b = b;
        if (people_dict.has(a)) {
            full_name_a = people_dict.get(a).full_name;
        }
        if (people_dict.has(b)) {
            full_name_b = people_dict.get(b).full_name;
        }
        return util.strcmp(full_name_a, full_name_b);
    });

    return users;
}

// for testing:
exports._sort_users = sort_users;

function focus_lost() {
    if (!exports.has_focus) {
        return false;
    }

    exports.has_focus = false;
}

function update_users() {
    var users = sort_users(Object.keys(user_info), user_info);
    ui.set_presence_list(users, user_info);
}

function status_from_timestamp(baseline_time, presence) {
    if (presence.website === undefined) {
        return 'offline';
    }

    var age = baseline_time - presence.website.timestamp;

    var status = 'offline';
    if (age < OFFLINE_THRESHOLD_SECS) {
        status = presence.website.status;
    }
    return status;
}

function focus_ping() {
    $.post('/json/update_active_status',
            {status: (exports.has_focus) ? exports.ACTIVE : exports.IDLE}, function (data) {
        if (data === undefined || data.presences === undefined) {
            // We sometimes receive no data even on successful
            // requests; we should figure out why but this will
            // prevent us from throwing errors until then
            return;
        }

        user_info = {};

        // Update Zephyr mirror activity warning
        if (data.zephyr_mirror_active === false) {
            $('#zephyr-mirror-error').show();
        } else {
            $('#zephyr-mirror-error').hide();
        }

        // Ping returns the active peer list
        _.each(data.presences, function (presence, this_email) {
            if (page_params.email !== this_email) {
                user_info[this_email] = status_from_timestamp(data.server_timestamp, presence);
            }
        });
        update_users();
    });
}

function focus_gained() {
    if (!exports.has_focus) {
        exports.has_focus = true;

        focus_ping();
    }
}

exports.initialize = function () {
    $(window).focus(focus_gained);
    $(window).idle({idle: DEFAULT_IDLE_TIMEOUT_MS,
                onIdle: focus_lost,
                onActive: focus_gained,
                keepTracking: true});

    setInterval(focus_ping, ACTIVE_PING_INTERVAL_MS);

    focus_ping();
};

// Set user statuses. `users` should be an object with user emails as keys
// and presence information (see `status_from_timestamp`) as values.
//
// The object does not need to include every user, only the ones
// whose presence you wish to update.
//
// This rerenders the user sidebar at the end, which can be slow if done too
// often, so try to avoid calling this repeatedly.
exports.set_user_statuses = function (users, server_time) {
    _.each(users, function (presence, email) {
        if (email === page_params.email) {
            return;
        }
        user_info[email] = status_from_timestamp(server_time, presence);
    });

    update_users();
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = activity;
}
