var activity = (function () {
var exports = {};

/*
    Helpers for detecting user activity and managing user idle states
*/

/* After this amount of no activity, mark you idle regardless of your focus */
var DEFAULT_IDLE_TIMEOUT_MS = 30 * 60 * 1000;
/* Time between keep-alive pings */
var ACTIVE_PING_INTERVAL_MS = 60 * 1000;

/* Timeouts for away and idle state */
var AWAY_THRESHOLD_SECS = 10 * 60;
var IDLE_THRESHOLD_SECS = DEFAULT_IDLE_TIMEOUT_MS / 1000;

/* Keep in sync with views.py:json_update_active_status() */
var ACTIVE = "active";
var IDLE = "idle";

var has_focus = true;
var ping_timer;

var user_info = {};

function sort_users(users, user_info) {
    // TODO sort by unread count first, once we support that
    users.sort(function (a, b) {
        if (user_info[a] === 'active' && user_info[b] !== 'active') {
            return -1;
        } else if (user_info[b] === 'active' && user_info[a] !== 'active') {
            return 1;
        }

        if (user_info[a] === 'away' && user_info[b] !== 'away') {
            return -1;
        } else if (user_info[b] === 'away' && user_info[a] !== 'away') {
            return 1;
        }

        // Sort equivalent PM names alphabetically
        var full_name_a = a;
        var full_name_b = b;
        if (people_dict[a] !== undefined) {
            full_name_a = people_dict[a].full_name;
        }
        if (people_dict[b] !== undefined) {
            full_name_b = people_dict[b].full_name;
        }
        return full_name_a.localeCompare(full_name_b);
    });

    return users;
}

function focus_lost() {
    if (!has_focus) {
        return false;
    }

    has_focus = false;

    clearInterval(ping_timer);
    ping_timer = undefined;

    $.post('/json/update_active_status', {status: IDLE});

}

function update_users() {
    var users = sort_users(Object.keys(user_info), user_info);
    ui.set_presence_list(users, user_info);
}

function status_from_timestamp(time_now, presence) {
    if (presence.website === undefined) {
        return 'idle';
    }

    var age = time_now - presence.website.timestamp;

    var status = 'idle';
    if (presence.website.status === ACTIVE && age >= 0) {
        if (age < AWAY_THRESHOLD_SECS) {
            status = 'active';
        } else if (age < IDLE_THRESHOLD_SECS) {
            status = 'away';
        }
    }
    return status;
}

function focus_ping() {
    if (!has_focus) {
        return;
    }

    $.post('/json/update_active_status', {status: ACTIVE}, function (data) {
        var now = new Date().getTime() / 1000;
        user_info = {};

        // Update Zephyr mirror activity warning
        if (data.zephyr_mirror_active === false) {
            $('#zephyr-mirror-error').show();
        } else {
            $('#zephyr-mirror-error').hide();
        }

        // Ping returns the active peer list
        $.each(data.presences, function (this_email, presence) {
            if (page_params.email !== this_email) {
                user_info[this_email] = status_from_timestamp(now, presence);
            }
        });
        update_users();
    });
}

function focus_gained() {
    if (!has_focus) {
        has_focus = true;
        ping_timer = setInterval(focus_ping, ACTIVE_PING_INTERVAL_MS);

        focus_ping();
    }
}

exports.initialize = function () {
    $(window).focus(focus_gained);
    $(window).idle({idle: DEFAULT_IDLE_TIMEOUT_MS,
                onIdle: focus_lost,
                onActive: focus_gained,
                keepTracking: true});

    ping_timer = setInterval(focus_ping, ACTIVE_PING_INTERVAL_MS);

    focus_ping();
};

exports.set_user_status = function (user_email, presence) {
    if (user_email === page_params.email) {
        return;
    }
    var now = new Date().getTime() / 1000;
    user_info[user_email] = status_from_timestamp(now, presence);

    update_users();
};

return exports;

}());
