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
 * Keep in sync with zerver/tornado/event_queue.py:receiver_is_idle
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

function update_count_in_dom(count_span, value_span, count) {
    if (count === 0) {
        count_span.hide();
        if (count_span.parent().hasClass("user_sidebar_entry")) {
            count_span.parent(".user_sidebar_entry").removeClass("user-with-count");
        } else if (count_span.parent().hasClass("group-pms-sidebar-entry")) {
            count_span.parent(".group-pms-sidebar-entry").removeClass("group-with-count");
        }
        value_span.text('');
        return;
    }

    count_span.show();

    if (count_span.parent().hasClass("user_sidebar_entry")) {
        count_span.parent(".user_sidebar_entry").addClass("user-with-count");
    } else if (count_span.parent().hasClass("group-pms-sidebar-entry")) {
        count_span.parent(".group-pms-sidebar-entry").addClass("group-with-count");
    }
    value_span.text(count);
}

function get_filter_li(user_ids_string) {
    if (name.indexOf(",") < 0) {
        return $("li.user_sidebar_entry[data-user-id='" + user_ids_string + "']");
    }
    return $("li.group-pms-sidebar-entry[data-user-ids='" + user_ids_string + "']");
}

function set_count(user_ids_string, count) {
    var count_span = get_filter_li(user_ids_string).find('.count');
    var value_span = count_span.find('.value');
    update_count_in_dom(count_span, value_span, count);
}

exports.update_dom_with_unread_counts = function (counts) {
    // counts is just a data object that gets calculated elsewhere
    // Our job is to update some DOM elements.

    counts.pm_count.each(function (count, user_ids_string) {
        // TODO: just use user_ids_string in our markup
        set_count(user_ids_string, count);
    });
};

exports.process_loaded_messages = function (messages) {
    var need_resize = false;

    _.each(messages, function (message) {
        if (message.type === 'private') {
            if (message.reply_to.indexOf(',') > 0) {
                var user_ids_string = people.emails_strings_to_user_ids_string(
                    message.reply_to);

                if (!user_ids_string) {
                    blueslip.warn('Bad reply_to for huddle: ' + message.reply_to);
                }

                var old_timestamp = huddle_timestamps.get(user_ids_string);

                if (!old_timestamp || (old_timestamp < message.timestamp)) {
                    huddle_timestamps.set(user_ids_string, message.timestamp);
                    need_resize = true;
                }
            }
        }
    });

    exports.update_huddles();

    if (need_resize) {
        resize.resize_page_components(); // big hammer
    }
};

exports.get_huddles = function () {
    var huddles = huddle_timestamps.keys();
    huddles = _.sortBy(huddles, function (huddle) {
        return huddle_timestamps.get(huddle);
    });
    return huddles.reverse();
};

exports.full_huddle_name = function (huddle) {
    var user_ids = huddle.split(',');

    var names = _.map(user_ids, function (user_id) {
        var person = people.get_person_from_user_id(user_id);
        return person.full_name;
    });

    return names.join(', ');
};

exports.short_huddle_name = function (huddle) {
    var user_ids = huddle.split(',');

    var num_to_show = 3;
    var names = _.map(user_ids, function (user_id) {
        var person = people.get_person_from_user_id(user_id);
        return person.full_name;
    });

    names = _.sortBy(names, function (name) { return name.toLowerCase(); });
    names = names.slice(0, num_to_show);
    var others = user_ids.length - num_to_show;

    if (others === 1) {
        names.push("+ 1 other");
    } else if (others >= 2) {
        names.push("+ " + others + " others");
    }

    return names.join(', ');
};

exports.huddle_fraction_present = function (huddle, presence_info) {
    var user_ids = huddle.split(',');

    var num_present = 0;
    _.each(user_ids, function (user_id) {
        if (presence_info[user_id]) {
            var status = presence_info[user_id].status;
            if (status && (status !== 'offline')) {
                num_present += 1;
            }
        }
    });

    var ratio = num_present / user_ids.length;

    return ratio.toFixed(2);
};

function sort_users(user_ids, presence_info) {
    // TODO sort by unread count first, once we support that
    user_ids.sort(function (a, b) {
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
        if (people.get_person_from_user_id(a)) {
            full_name_a = people.get_person_from_user_id(a).full_name;
        }
        if (people.get_person_from_user_id(b)) {
            full_name_b = people.get_person_from_user_id(b).full_name;
        }
        return util.strcmp(full_name_a, full_name_b);
    });

    return user_ids;
}

// for testing:
exports._sort_users = sort_users;

function focus_lost() {
    if (!exports.has_focus) {
        return false;
    }

    exports.has_focus = false;
}

function filter_user_ids(user_ids) {
    var user_list = $(".user-list-filter");
    if (user_list.length === 0) {
        // We may have received an activity ping response after
        // initiating a reload, in which case the user list may no
        // longer be available.
        // Return user list: useful for testing user list performance fix
        return user_ids;
    }

    var search_term = user_list.expectOne().val().trim();
    if (search_term === '') {
        return user_ids;
    }

    var search_terms = search_term.toLowerCase().split(",");
    search_terms = _.map(search_terms, function (s) {
        return s.trim();
    });

    var persons = _.map(user_ids, function (user_id) {
        return people.get_person_from_user_id(user_id);
    });

    var email_dict = people.filter_people_by_search_terms(persons, search_terms);
    user_ids = _.map(_.keys(email_dict), function (email) {
        return people.get_user_id(email);
    });
    return user_ids;
}

function filter_and_sort(users) {
    var user_ids = Object.keys(users);
    user_ids = filter_user_ids(user_ids);
    user_ids = sort_users(user_ids, exports.presence_info);
    return user_ids;
}

exports._filter_and_sort = filter_and_sort;

exports.update_users = function (user_list) {
    if (page_params.presence_disabled) {
        return;
    }

    var users = exports.presence_info;
    var all_users;
    if (user_list !== undefined) {
        all_users = filter_and_sort(users);
        users = user_list;
    }
    users = filter_and_sort(users);

    function get_num_unread(user_id) {
        if (unread.suppress_unread_counts) {
            return 0;
        }
        return unread.num_unread_for_person(user_id);
    }

    // Note that we do not include ourselves in the user list any more.
    // If you want to figure out how to get details for "me", then revert
    // the commit that added this comment.

    function info_for(user_id) {
        var presence = exports.presence_info[user_id].status;
        var person = people.get_person_from_user_id(user_id);
        return {
            name: person.full_name,
            user_id: user_id,
            num_unread: get_num_unread(user_id),
            type: presence,
            type_desc: presence_descriptions[presence],
            mobile: exports.presence_info[user_id].mobile
        };
    }

    var user_info = _.map(users, info_for);
    if (user_list !== undefined) {
        // Render right panel partially
        _.each(user_info, function (user) {
            var user_index = all_users.indexOf(user.user_id);
            $('#user_presences').find('[data-user-id="' + user.user_id + '"]').remove();
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

function show_huddles() {
    $('#group-pm-list').addClass("show");
}

function hide_huddles() {
    $('#group-pm-list').removeClass("show");
}

exports.update_huddles = function () {
    if (page_params.presence_disabled) {
        return;
    }

    var huddles = exports.get_huddles().slice(0, 10);

    if (huddles.length === 0) {
        hide_huddles();
        return;
    }

    var group_pms = _.map(huddles, function (huddle) {
        return {
            user_ids_string: huddle,
            name: exports.full_huddle_name(huddle),
            fraction_present: exports.huddle_fraction_present(huddle, exports.presence_info),
            short_name: exports.short_huddle_name(huddle)
        };
    });

    var html = templates.render('group_pms', {group_pms: group_pms});
    $('#group-pms').expectOne().html(html);

    _.each(huddles, function (user_ids_string) {
        var count = unread.num_unread_for_person(user_ids_string);
        set_count(user_ids_string, count);
    });

    show_huddles();
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
                    blueslip.error('Unexpected status', {presence_object: device_presence, device: device}, undefined);
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
                    var user_id = people.get_user_id(this_email);
                    if (user_id) {
                        var status = status_from_timestamp(data.server_timestamp,
                                                           presence);
                        exports.presence_info[user_id] = status;
                    }
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

    activity.set_user_statuses(page_params.initial_presences,
                               page_params.initial_servertime);
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
        var user_id = people.get_user_id(email);
        if (user_id) {
            exports.presence_info[user_id] = status;
            updated_users[user_id] = status;
        } else {
            blueslip.warn('unknown email: ' + email);
        }
    });

    exports.update_users(updated_users);
    exports.update_huddles();
};

exports.redraw = function () {
    exports.update_users();
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

function maybe_select_person(e) {
    if (e.keyCode === 13) {
        // Enter key was pressed

        // Prevent a newline from being entered into the soon-to-be-opened composebox
        e.preventDefault();

        var topPerson = $('#user_presences li.user_sidebar_entry').first().attr('data-user-id');
        var user_list = $(".user-list-filter");
        var search_term = user_list.expectOne().val().trim();
        if ((topPerson !== undefined) && (search_term !== '')) {
            // undefined if there are no results
            var email = people.get_person_from_user_id(topPerson).email;
            compose.start('private',
                    {trigger: 'sidebar enter key', private_message_recipient: email});
        }
        // Clear the user filter
        exports.escape_search();
    }
}

function focus_user_filter(e) {
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
