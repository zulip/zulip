var activity = (function () {

/*
    Helpers for detecting user activity and managing user idle states
*/

/* 5 minutes after no activity, idle regardless of focus */
var DEFAULT_IDLE_TIMEOUT = 5 * 60 * 1000 ;
/* 1 minute between keep-alive pings */
var ACTIVE_PING_INTERVAL = 60 * 1000;
/* Twice the ping interval is the cutoff for dead clients */
var IDLE_THRESHOLD_SECS = 2 * ACTIVE_PING_INTERVAL / 1000;

/* Keep in sync with views.py:json_update_active_status() */
var ACTIVE = "active";
var IDLE = "idle";

var has_focus = true;
var ping_timer;

var exports = {};


function sort_users(users, user_info) {
    // TODO sort by unread count first, once we support that
    users.sort(function (a, b) {
        if (user_info[a] && !user_info[b]) {
            return -1;
        } else if (user_info[b] && !user_info[a]) {
            return 1;
        }

        // Sort equivalent PM names alphabetically
        if (a < b) {
            return -1;
        } else if (a === b) {
            return 0;
        } else {
            return 1;
        }
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
                var active = presence.website !== undefined && presence.website.status === ACTIVE &&
                                age >= 0 && age < IDLE_THRESHOLD_SECS;
                user_info[this_email] = active;
            }
        });
        users = sort_users(Object.keys(user_info), user_info);
        ui.set_presence_list(users, user_info);
    });
}

function focus_gained() {
    if (!has_focus) {
        has_focus = true;
        ping_timer = setInterval(focus_ping, ACTIVE_PING_INTERVAL);

        focus_ping();
    }
}

exports.initialize = function () {
    $(window).focus(focus_gained);
    $(window).idle({idle: DEFAULT_IDLE_TIMEOUT,
                onIdle: focus_lost,
                onActive: focus_gained,
                keepTracking: true});

    ping_timer = setInterval(focus_ping, ACTIVE_PING_INTERVAL);

    focus_ping();
};

return exports;

}());
