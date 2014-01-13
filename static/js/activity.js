var activity = (function () {
var exports = {};

/*
    Helpers for detecting user activity and managing user idle states
*/

/* Broadcast "idle" to server after 5 minutes of local inactivity */
var DEFAULT_IDLE_TIMEOUT_MS = 5 * 60 * 1000;
/* Time between keep-alive pings */
var ACTIVE_PING_INTERVAL_MS = 50 * 1000;

/* Mark users as offline after 140 seconds since their last checkin */
var OFFLINE_THRESHOLD_SECS = 140;


var presence_descriptions = {
    active: 'is active',
    idle:   'is not active'
};

/* Keep in sync with views.py:json_update_active_status() */
exports.ACTIVE = "active";
exports.IDLE = "idle";

// When you start Zulip, has_focus should be true, but it might not be the
// case after a server-initiated reload.
exports.has_focus = document.hasFocus && document.hasFocus();

// We initialize this to true, to count new page loads, but set it to
// false in the onload function in reload.js if this was a
// server-initiated-reload to avoid counting a server-initiated reload
// as user activity.
exports.new_user_input = true;

$("html").on("mousemove", function () {
    exports.new_user_input = true;
});

var presence_info = {};

var huddle_timestamps = new Dict();

exports.process_loaded_messages = function (messages) {
    _.each(messages, function (message) {
        if (message.type === 'private') {
            if (message.reply_to.indexOf(',') > 0) {
                var old_timestamp = huddle_timestamps.get(message.reply_to);

                if (!old_timestamp || (old_timestamp < message.timestamp)) {
                    huddle_timestamps.set(message.reply_to, message.timestamp);
                }
            }
        }
    });
};

exports.get_huddles = function () {
    var huddles = huddle_timestamps.keys();
    huddles = _.sortBy(huddles, function (huddle) {
        return huddle_timestamps.get(huddle);
    });
    return huddles.reverse();
};

exports.full_huddle_name = function (huddle) {
    var emails = huddle.split(',');

    var names = _.map(emails, function (email) {
        var person = people_dict.get(email);
        return person ? person.full_name : email;
    });

    return names.join(', ');
};

exports.short_huddle_name = function (huddle) {
    var emails = huddle.split(',');

    var num_to_show = 3;
    var names = _.map(emails.slice(0, num_to_show), function (email) {
        var person = people_dict.get(email);
        return person ? person.full_name : email;
    });
    var others = emails.length - num_to_show;

    if (others === 1) {
        names.push("+ 1 other");
    } else if (others >= 2) {
        names.push("+ " + others + " others");
    }

    return names.join(', ');
};

exports.huddle_fraction_present = function (huddle, presence_info) {
    var emails = huddle.split(',');

    var num_present = 0;
    _.each(emails, function (email) {
        var status = presence_info[email];
        if (status && (status !== 'offline')) {
            ++num_present;
        }
    });

    var ratio = num_present / emails.length;

    return ratio.toFixed(2);
};

function sort_users(users, presence_info) {
    // TODO sort by unread count first, once we support that
    users.sort(function (a, b) {
        if (presence_info[a] === 'active' && presence_info[b] !== 'active') {
            return -1;
        } else if (presence_info[b] === 'active' && presence_info[a] !== 'active') {
            return 1;
        }

        if (presence_info[a] === 'idle' && presence_info[b] !== 'idle') {
            return -1;
        } else if (presence_info[b] === 'idle' && presence_info[a] !== 'idle') {
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

function filter_users_by_search(users) {
    var search_term = $(".user-list-filter").expectOne().val().trim();

    if (search_term === '') {
        return users;
    }

    var search_terms = search_term.toLowerCase().split(",");
    search_terms = _.map(search_terms, function (s) {
        return s.trim();
    });

    var filtered_users = _.filter(users, function (user) {
        var person = people_dict.get(user);
        if (!person || !person.full_name) {
            return false;
        }
        var names = person.full_name.toLowerCase().split();
        names = _.map(names, function (s) {
            return s.trim();
        });
        return _.any(search_terms, function (search_term) {
            return _.any(names, function (name) {
                return name.indexOf(search_term) === 0;
            });
        });
    });

    return filtered_users;
}

function actually_update_users() {
    if (page_params.domain === 'mit.edu') {
        return;  // MIT realm doesn't have a presence list
    }

    var users = Object.keys(presence_info);
    users = filter_users_by_search(users);
    users = sort_users(users, presence_info);

    function get_num_unread(email) {
        if (suppress_unread_counts) {
            return 0;
        }
        return unread.num_unread_for_person(email);
    }

    var my_info = {
        name: page_params.fullname,
        email: page_params.email,
        num_unread: get_num_unread(page_params.email),
        type: (activity.has_focus) ? activity.ACTIVE : activity.IDLE,
        type_desc: presence_descriptions.active,
        my_fullname: true
    };

    function info_for(email) {
        var presence = presence_info[email];
        return {
            name: people_dict.get(email).full_name,
            email: email,
            num_unread: get_num_unread(email),
            type: presence,
            type_desc: presence_descriptions[presence]
        };
    }

    var user_emails = _.filter(users, function (email) {
        return people_dict.has(email);
    });

    var user_info = [my_info].concat(_.map(user_emails, info_for));

    $('#user_presences').html(templates.render('user_presence_rows', {users: user_info}));

    // Update user fading, if necessary.
    compose_fade.update_faded_users();
}

// The function actually_update_users() can be pretty expensive for realms with lots
// of users.  Not only is there more work to do in terms of rendering the user list, but
// we also get more updates.  Large realms have reported lags while typing in the compose
// box, and there's strong evidence that this is caused by user list updates.  This isn't a
// perfect solution, but it should remove some pain, and there's no real harm in waiting five
// seconds to update user activity.
var update_users = _.throttle(actually_update_users, 5000);


function actually_update_users_for_search() {
    actually_update_users();
    ui.resize_page_components();
}

var update_users_for_search = _.throttle(actually_update_users_for_search, 50);

exports.update_huddles = function () {
    if (page_params.domain === 'mit.edu') {
        return;  // MIT realm doesn't have a presence list
    }

    var section = $('#group-pm-list').expectOne();

    var huddles = exports.get_huddles().slice(0, 10);

    if (huddles.length === 0) {
        section.hide();
        return;
    }

    var group_pms = _.map(huddles, function (huddle) {
        return {
            emails: huddle,
            name: exports.full_huddle_name(huddle),
            fraction_present: exports.huddle_fraction_present(huddle, presence_info),
            short_name: exports.short_huddle_name(huddle)
        };
    });

    var html = templates.render('group_pms', {group_pms: group_pms});
    $('#group-pms').expectOne().html(html);

    _.each(huddles, function (huddle) {
        var count = unread.num_unread_for_person(huddle);
        stream_list.set_presence_list_count(huddle, count);
    });

    section.show();
};

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
    channel.post({
        url: '/json/update_active_status',
        data: {status: (exports.has_focus) ? exports.ACTIVE : exports.IDLE,
               new_user_input: exports.new_user_input},
        idempotent: true,
        success: function (data) {
            presence_info = {};

            // Update Zephyr mirror activity warning
            if (data.zephyr_mirror_active === false) {
                $('#zephyr-mirror-error').show();
            } else {
                $('#zephyr-mirror-error').hide();
            }

            exports.new_user_input = false;

            // Ping returns the active peer list
            _.each(data.presences, function (presence, this_email) {
                if (page_params.email !== this_email) {
                    presence_info[this_email] = status_from_timestamp(data.server_timestamp, presence);
                }
            });
            update_users();
            exports.update_huddles();
        }
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
        presence_info[email] = status_from_timestamp(server_time, presence);
    });

    update_users();
    exports.update_huddles();
};


$(function () {
    $(".user-list-filter").expectOne().on('input', update_users_for_search);
});


return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = activity;
}
