var activity = (function () {
var exports = {};

/*
    Helpers for detecting user activity and managing user idle states
*/

/* Broadcast "idle" to server after 5 minutes of local inactivity */
var DEFAULT_IDLE_TIMEOUT_MS = 5 * 60 * 1000;
/* Time between keep-alive pings */
var ACTIVE_PING_INTERVAL_MS = 50 * 1000;

var presence_descriptions = {
    active: 'is active',
    idle:   'is not active',
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

var huddle_timestamps = new Dict();

function update_pm_count_in_dom(count_span, value_span, count) {
    var li = count_span.parent();

    if (count === 0) {
        count_span.hide();
        li.removeClass("user-with-count");
        value_span.text('');
        return;
    }

    count_span.show();
    li.addClass("user-with-count");
    value_span.text(count);
}

function update_group_count_in_dom(count_span, value_span, count) {
    var li = count_span.parent();

    if (count === 0) {
        count_span.hide();
        li.removeClass("group-with-count");
        value_span.text('');
        return;
    }

    count_span.show();
    li.addClass("group-with-count");
    value_span.text(count);
}

function get_pm_list_item(user_id) {
    return $("li.user_sidebar_entry[data-user-id='" + user_id + "']");
}

function get_group_list_item(user_ids_string) {
    return $("li.group-pms-sidebar-entry[data-user-ids='" + user_ids_string + "']");
}

function set_pm_count(user_ids_string, count) {
    var count_span = get_pm_list_item(user_ids_string).find('.count');
    var value_span = count_span.find('.value');
    update_pm_count_in_dom(count_span, value_span, count);
}

function set_group_count(user_ids_string, count) {
    var count_span = get_group_list_item(user_ids_string).find('.count');
    var value_span = count_span.find('.value');
    update_group_count_in_dom(count_span, value_span, count);
}

exports.update_dom_with_unread_counts = function (counts) {
    // counts is just a data object that gets calculated elsewhere
    // Our job is to update some DOM elements.

    counts.pm_count.each(function (count, user_ids_string) {
        // TODO: just use user_ids_string in our markup
        var is_pm = user_ids_string.indexOf(',') < 0;
        if (is_pm) {
            set_pm_count(user_ids_string, count);
        } else {
            set_group_count(user_ids_string, count);
        }
    });
};

exports.process_loaded_messages = function (messages) {
    var need_resize = false;

    _.each(messages, function (message) {
        var huddle_string = people.huddle_string(message);

        if (huddle_string) {
            var old_timestamp = huddle_timestamps.get(huddle_string);

            if (!old_timestamp || (old_timestamp < message.timestamp)) {
                huddle_timestamps.set(huddle_string, message.timestamp);
                need_resize = true;
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

exports.huddle_fraction_present = function (huddle) {
    var user_ids = huddle.split(',');

    var num_present = 0;
    _.each(user_ids, function (user_id) {
        if (presence.is_not_offline(user_id)) {
            num_present += 1;
        }
    });

    var ratio = num_present / user_ids.length;

    return ratio.toFixed(2);
};

function compare_function(a, b) {

    function level(status) {
        switch (status) {
            case 'active':
                return 1;
            case 'idle':
                return 2;
            default:
                return 3;
        }
    }

    var level_a = level(presence.get_status(a));
    var level_b = level(presence.get_status(b));
    var diff = level_a - level_b;
    if (diff !== 0) {
        return diff;
    }

    // Sort equivalent PM names alphabetically
    var person_a = people.get_person_from_user_id(a);
    var person_b = people.get_person_from_user_id(b);

    var full_name_a = person_a ? person_a.full_name : '';
    var full_name_b = person_b ? person_b.full_name : '';

    return util.strcmp(full_name_a, full_name_b);
}

function sort_users(user_ids) {
    // TODO sort by unread count first, once we support that
    user_ids.sort(compare_function);
    return user_ids;
}

// for testing:
exports._sort_users = sort_users;

function focus_lost() {
    // When we become idle, we don't immediately send anything to the
    // server; instead, we wait for our next periodic update, since
    // this data is fundamentally not timely.
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

    var user_id_dict = people.filter_people_by_search_terms(persons, search_terms);
    return user_id_dict.keys();
}

function matches_filter(user_id) {
    // This is a roundabout way of checking a user if you look
    // too hard at it, but it should be fine for now.
    return (filter_user_ids([user_id]).length === 1);
}

function filter_and_sort(user_ids) {
    user_ids = filter_user_ids(user_ids);
    user_ids = sort_users(user_ids);
    return user_ids;
}

exports._filter_and_sort = filter_and_sort;

function get_num_unread(user_id) {
    if (unread.suppress_unread_counts) {
        return 0;
    }
    return unread.num_unread_for_person(user_id);
}

function info_for(user_id) {
    var status = presence.get_status(user_id);
    var person = people.get_person_from_user_id(user_id);
    return {
        href: narrow.pm_with_uri(person.email),
        name: person.full_name,
        user_id: user_id,
        num_unread: get_num_unread(user_id),
        type: status,
        type_desc: presence_descriptions[status],
        mobile: presence.get_mobile(user_id),
    };
}

exports.insert_user_into_list = function (user_id) {
    if (page_params.realm_presence_disabled) {
        return;
    }

    if (!matches_filter(user_id)) {
        return;
    }

    var info = info_for(user_id);
    $('#user_presences').find('[data-user-id="' + user_id + '"]').remove();
    var html = templates.render('user_presence_row', info);

    var items = $('#user_presences li').toArray();

    function insert() {
        var i = 0;

        for (i = 0; i < items.length; i += 1) {
            var li = $(items[i]);
            var list_user_id = li.attr('data-user-id');
            if (compare_function(user_id, list_user_id) < 0) {
                li.before(html);
                return;
            }
        }

        $('#user_presences').append(html);
    }

    insert();

    var elt = get_pm_list_item(user_id);
    compose_fade.update_one_user_row(elt);
};

exports.build_user_sidebar = function () {
    if (page_params.realm_presence_disabled) {
        return;
    }

    var user_ids = filter_and_sort(presence.get_user_ids());

    var user_info = _.map(user_ids, info_for);
    var html = templates.render('user_presence_rows', {users: user_info});
    $('#user_presences').html(html);

    // Update user fading, if necessary.
    compose_fade.update_faded_users();

    resize.resize_page_components();

    return user_info; // for testing
};

function actually_update_users_for_search() {
    exports.build_user_sidebar();
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
    if (page_params.realm_presence_disabled) {
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
            href: narrow.huddle_with_uri(huddle),
            fraction_present: exports.huddle_fraction_present(huddle),
            short_name: exports.short_huddle_name(huddle),
        };
    });

    var html = templates.render('group_pms', {group_pms: group_pms});
    $('#group-pms').expectOne().html(html);

    _.each(huddles, function (user_ids_string) {
        var count = unread.num_unread_for_person(user_ids_string);
        set_group_count(user_ids_string, count);
    });

    show_huddles();
};


function focus_ping(want_redraw) {
    channel.post({
        url: '/json/users/me/presence',
        data: {status: (exports.has_focus) ? exports.ACTIVE : exports.IDLE,
               ping_only: !want_redraw,
               new_user_input: exports.new_user_input},
        idempotent: true,
        success: function (data) {

            // Update Zephyr mirror activity warning
            if (data.zephyr_mirror_active === false) {
                $('#zephyr-mirror-error').addClass("show");
            } else {
                $('#zephyr-mirror-error').removeClass("show");
            }

            exports.new_user_input = false;

            // Zulip has 2 data feeds coming from the server to the
            // client: The server_events data, and this presence feed.
            // Everything in server_events is nicely serialized, but
            // if we've been offline and not running for a while
            // (e.g. due to suspend), we can end up throwing
            // exceptions due to users appearing in presence that we
            // haven't learned about yet.  We handle this in 2 stages.
            // First, here, we make sure that we've confirmed whether
            // we are indeed in the unsuspend case.  Then, in
            // `presence.set_info`, we only complain about unknown
            // users if server_events does not suspect we're offline.
            server_events.check_for_unsuspend();

            if (want_redraw) {
                presence.set_info(data.presences, data.server_timestamp);
                exports.build_user_sidebar();
                exports.update_huddles();
            }
        },
    });
}

function focus_gained() {
    if (!exports.has_focus) {
        exports.has_focus = true;
        focus_ping(false);
    }
}

exports.initialize = function () {
    $("html").on("mousemove", function () {
        exports.new_user_input = true;
    });

    $(window).focus(focus_gained);
    $(window).idle({idle: DEFAULT_IDLE_TIMEOUT_MS,
                onIdle: focus_lost,
                onActive: focus_gained,
                keepTracking: true});

    presence.set_info(page_params.presences,
                      page_params.initial_servertime);
    delete page_params.presences;

    exports.build_user_sidebar();
    exports.update_huddles();

    // Let the server know we're here, but pass "false" for
    // want_redraw, since we just got all this info in page_params.
    focus_ping(false);

    function get_full_presence_list_update() {
        focus_ping(true);
    }

    setInterval(get_full_presence_list_update, ACTIVE_PING_INTERVAL_MS);
};

exports.set_user_status = function (email, info, server_time) {
    if (people.is_current_user(email)) {
        return;
    }

    var user_id = people.get_user_id(email);
    if (!user_id) {
        blueslip.warn('unknown email: ' + email);
        return;
    }

    presence.set_user_status(user_id, info, server_time);
    exports.insert_user_into_list(user_id);
    exports.update_huddles();
};

exports.redraw = function () {
    exports.build_user_sidebar();
    exports.update_huddles();
};

exports.searching = function () {
    return $('.user-list-filter').expectOne().is(':focus');
};

function update_clear_search_button() {
    var focused = $('.user-list-filter').is(':focus');

    // Show button iff the search input is focused, or has non-empty contents
    if (focused || $('.user-list-filter').val()) {
        $('#clear_search_people_button').removeAttr('disabled');
    } else {
        $('#clear_search_people_button').attr('disabled', 'disabled');
    }
}

exports.escape_search = function () {
    var filter = $('.user-list-filter').expectOne();
    if (filter.val() === '') {
        filter.blur();
        return;
    }
    filter.val('');
    update_clear_search_button();
    update_users_for_search();
};

exports.initiate_search = function () {
    var filter = $('.user-list-filter').expectOne();
    filter.focus();
};

exports.blur_search = function () {
    $('.user-list-filter').blur();
    update_clear_search_button();
};

exports.clear_search = function () {
    $('.user-list-filter').val('');
    $('.user-list-filter').blur();
    update_clear_search_button();
    update_users_for_search();
};

function maybe_select_person(e) {
    if (e.keyCode === 13) {
        // Enter key was pressed

        // Prevent a newline from being entered into the soon-to-be-opened composebox
        e.preventDefault();
        e.stopPropagation();

        var topPerson = $('#user_presences li.user_sidebar_entry').first().attr('data-user-id');
        var user_list = $(".user-list-filter");
        var search_term = user_list.expectOne().val().trim();
        if ((topPerson !== undefined) && (search_term !== '')) {
            // undefined if there are no results
            var email = people.get_person_from_user_id(topPerson).email;
            narrow.by('pm-with', email, {select_first_unread: true, trigger: 'user sidebar'});
            compose_actions.start('private', {
                trigger: 'sidebar enter key',
                private_message_recipient: email});
        }
        // Clear the user filter
        exports.escape_search();
    }
}

function focus_user_filter(e) {
    e.stopPropagation();
    update_clear_search_button();
}

$(function () {
    $(".user-list-filter").expectOne()
        .on('click', focus_user_filter)
        .on('input', update_users_for_search)
        .on('keydown', maybe_select_person)
        .on('blur', update_clear_search_button);
    $('#clear_search_people_button').on('click', exports.clear_search);
});


return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = activity;
}
