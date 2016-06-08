var activity = (function () {
var exports = {};

/*
    Helpers for detecting user activity and managing user idle states
*/

/* Broadcast "idle" to server after 5 minutes of local inactivity */
var DEFAULT_IDLE_TIMEOUT_MS = 5 * 60 * 1000;
/* Time between keep-alive pings */
var ACTIVE_PING_INTERVAL_MS = 50 * 1000;

/* Mark users as offline after 140 seconds since their last checkin,
 * Keep in sync with zerver/lib/event_queue.py:receiver_is_idle
 */
var OFFLINE_THRESHOLD_SECS = 140;

// Testing
exports._OFFLINE_THRESHOLD_SECS = OFFLINE_THRESHOLD_SECS;

var MOBILE_DEVICES = ["Android", "ZulipiOS", "ios"];

function is_mobile(device) {
    return MOBILE_DEVICES.indexOf(device) !== -1;
}

var presence_descriptions = {
    active: 'is active',
    idle:   'is not active'
};

/* Keep in sync with views.py:update_active_status_backend() */
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

exports.presence_info = {};

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
        var person = people.get_by_email(email);
        return person ? person.full_name : email;
    });

    return names.join(', ');
};

exports.short_huddle_name = function (huddle) {
    var emails = huddle.split(',');

    var num_to_show = 3;
    var names = _.map(emails.slice(0, num_to_show), function (email) {
        var person = people.get_by_email(email);
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
        if (presence_info[email]) {
            var status = presence_info[email].status;
            if (status && (status !== 'offline')) {
                ++num_present;
            }
        }
    });

    var ratio = num_present / emails.length;

    return ratio.toFixed(2);
};

function sort_users(users, presence_info) {
    // TODO sort by unread count first, once we support that
    users.sort(function (a, b) {
        if (presence_info[a].status === 'active' && presence_info[b].status !== 'active') {
            return -1;
        } else if (presence_info[b].status === 'active' && presence_info[a].status !== 'active') {
            return 1;
        }

        if (presence_info[a].status === 'idle' && presence_info[b].status !== 'idle') {
            return -1;
        } else if (presence_info[b].status === 'idle' && presence_info[a].status !== 'idle') {
            return 1;
        }

        // Sort equivalent PM names alphabetically
        var full_name_a = a;
        var full_name_b = b;
        if (people.get_by_email(a)) {
            full_name_a = people.get_by_email(a).full_name;
        }
        if (people.get_by_email(b)) {
            full_name_b = people.get_by_email(b).full_name;
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
    var user_list = $(".user-list-filter");
    if (user_list.length === 0) {
        // We may have received an activity ping response after
        // initiating a reload, in which case the user list may no
        // longer be available.
        // Return user list: useful for testing user list performance fix
        return users;
    }

    var search_term = user_list.expectOne().val().trim();

    if (search_term === '') {
        return users;
    }

    var search_terms = search_term.toLowerCase().split(",");
    search_terms = _.map(search_terms, function (s) {
        return s.trim();
    });

    var filtered_users = _.filter(users, function (user) {
        var person = people.get_by_email(user);
        if (!person || !person.full_name) {
            return false;
        }
        var names = person.full_name.toLowerCase().split(/\s+/);
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

function filter_and_sort(users) {
    users = Object.keys(users);
    users = filter_users_by_search(users);
    users = _.filter(users, function (email) {
        return people.get_by_email(email);
    });

    users = sort_users(users, exports.presence_info);
    return users;
}
exports._filter_and_sort = filter_and_sort;

exports.update_users = function (user_list) {
    if (page_params.domain === 'mit.edu') {
        return;  // MIT realm doesn't have a presence list
    }

    var users = exports.presence_info;
    var all_users;
    if (user_list !== undefined) {
        all_users = filter_and_sort(users);
        users = user_list;
    }
    users = filter_and_sort(users);

    function get_num_unread(email) {
        if (unread.suppress_unread_counts) {
            return 0;
        }
        return unread.num_unread_for_person(email);
    }

    // Note that we do not include ourselves in the user list any more.
    // If you want to figure out how to get details for "me", then revert
    // the commit that added this comment.

    function info_for(email) {
        var presence = exports.presence_info[email].status;
        return {
            name: people.get_by_email(email).full_name,
            email: email,
            num_unread: get_num_unread(email),
            type: presence,
            type_desc: presence_descriptions[presence],
            mobile: exports.presence_info[email].mobile
        };
    }

    var user_info = _.map(users, info_for);
    if (user_list !== undefined) {
        // Render right panel partially
        $.each(user_info, function (index, user) {
            var user_index = all_users.indexOf(user.email);
            $('#user_presences').find('[data-email="' + user.email + '"]').remove();
            $('#user_presences li').eq(user_index).before(templates.render('user_presence_row', user));
        });
    } else {
        $('#user_presences').html(templates.render('user_presence_rows', {users: user_info}));
    }

    // Update user fading, if necessary.
    compose_fade.update_faded_users();

    // Return updated users: useful for testing user performance fix
    return user_info;
};

function actually_update_users_for_search() {
    exports.update_users();
    resize.resize_page_components();
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
            fraction_present: exports.huddle_fraction_present(huddle, exports.presence_info),
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
    var status = 'offline';
    var mobileAvailable = false;
    var nonmobileAvailable = false;
    _.each(presence, function (device_presence, device) {
        var age = baseline_time - device_presence.timestamp;
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
                    blueslip.error('Unexpected status', {'presence_object': device_presence, 'device': device}, undefined);
            }
        }
    });
    return {status: status, mobile: !nonmobileAvailable && mobileAvailable };
}

// For testing
exports._status_from_timestamp = status_from_timestamp;

function focus_ping() {
    channel.post({
        url: '/json/users/me/presence',
        data: {status: (exports.has_focus) ? exports.ACTIVE : exports.IDLE,
               new_user_input: exports.new_user_input},
        idempotent: true,
        success: function (data) {
            exports.presence_info = {};

            // Update Zephyr mirror activity warning
            if (data.zephyr_mirror_active === false) {
                $('#zephyr-mirror-error').show();
            } else {
                $('#zephyr-mirror-error').hide();
            }

            exports.new_user_input = false;

            // Ping returns the active peer list
            _.each(data.presences, function (presence, this_email) {
                if (!util.is_current_user(this_email)) {
                    exports.presence_info[this_email] = status_from_timestamp(data.server_timestamp, presence);
                }
            });
            exports.update_users();
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
    var updated_users = {};
    var status;
    _.each(users, function (presence, email) {
        if (util.is_current_user(email)) {
            return;
        }
        status = status_from_timestamp(server_time, presence);
        exports.presence_info[email] = status;
        updated_users[email] = status;
    });

    exports.update_users(updated_users);
    exports.update_huddles();
};

exports.searching = function () {
    return $('.user-list-filter').expectOne().is(':focus');
};

exports.escape_search = function () {
    var filter = $('.user-list-filter').expectOne();
    if (filter.val() === '') {
        filter.blur();
        return;
    }
    filter.val('');
    update_users_for_search();
};

exports.initiate_search = function () {
    var filter = $('.user-list-filter').expectOne();
    filter.focus();
};

exports.blur_search = function () {
    $('.user-list-filter').blur();
};

function maybe_select_person (e) {
    if (e.keyCode === 13) {
        // Enter key was pressed

        // Prevent a newline from being entered into the soon-to-be-opened composebox
        e.preventDefault();

        var topPerson = $('#user_presences li.user_sidebar_entry').first().data('email');
        if (topPerson !== undefined) {
            // undefined if there are no results
            compose.start('private',
                    {trigger: 'sidebar enter key', "private_message_recipient": topPerson});
        }
        // Clear the user filter
        exports.escape_search();
    }
}

function focus_user_filter (e) {
    e.stopPropagation();
}

$(function () {
    $(".user-list-filter").expectOne()
        .on('click', focus_user_filter)
        .on('input', update_users_for_search)
        .on('keydown', maybe_select_person);
});


return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = activity;
}
