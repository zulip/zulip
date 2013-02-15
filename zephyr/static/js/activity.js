var activity = (function () {
var exports = {};

/*
    Helpers for detecting user activity and managing user idle states
*/

/* 15 minutes after no activity, idle regardless of focus */
var DEFAULT_IDLE_TIMEOUT_MS = 15 * 60 * 1000;
/* 1 minute between keep-alive pings */
var ACTIVE_PING_INTERVAL_MS = 60 * 1000;

/* Timeouts for away and idle state */
var AWAY_THRESHOLD_SECS = 5 * 60;
var IDLE_THRESHOLD_SECS = DEFAULT_IDLE_TIMEOUT_MS / 1000;

/* Keep in sync with views.py:json_update_active_status() */
var ACTIVE = "active";
var IDLE = "idle";
/* Client-side state constants */
exports.user_active = "active";
exports.user_away = "away";
exports.user_idle = "idle";

var has_focus = true;
var ping_timer;

function sort_users(users, user_info) {
    // TODO sort by unread count first, once we support that
    users.sort(function (a, b) {
        if (user_info[a] === exports.user_active && user_info[b] !== exports.user_active) {
            return -1;
        } else if (user_info[b] === exports.user_active && user_info[a] !== exports.user_active) {
            return 1;
        }

        if (user_info[a] === exports.user_away && user_info[b] !== exports.user_away) {
            return -1;
        } else if (user_info[b] === exports.user_away && user_info[a] !== exports.user_away) {
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

function focus_ping() {
    if (!has_focus) {
        return;
    }

    $.post('/json/update_active_status', {status: ACTIVE}, function (data) {
        var now = new Date().getTime() / 1000;
        var user_info = {};
        var users = [];

        // Ping returns the active peer list
        $.each(data.presences, function (this_email, presence) {
            var age = -1;

            if (presence.website !== undefined && presence.website.timestamp !== undefined) {
                age = now - presence.website.timestamp;
            }

            if (email !== this_email) {
                var status = exports.user_idle;
                if (presence.website !== undefined
                    && presence.website.status === ACTIVE && age >= 0) {
                    if (age < AWAY_THRESHOLD_SECS) {
                        status = exports.user_active;
                    } else if (age < IDLE_THRESHOLD_SECS) {
                        status = exports.user_away;
                    }
                }
                user_info[this_email] = status;
            }
        });
        users = sort_users(Object.keys(user_info), user_info);
        ui.set_presence_list(users, user_info);
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

return exports;

}());
