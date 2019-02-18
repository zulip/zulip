var activity = (function () {
var exports = {};

/*
    Helpers for detecting user activity and managing user idle states
*/

/* Broadcast "idle" to server after 5 minutes of local inactivity */
var DEFAULT_IDLE_TIMEOUT_MS = 5 * 60 * 1000;
/* Time between keep-alive pings */
var ACTIVE_PING_INTERVAL_MS = 50 * 1000;

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

exports.update_scrollbar = (function () {
    var $buddy_list_wrapper = $("#buddy_list_wrapper");
    var $group_pms = $("#group-pms");

    return {
        users: function () {
            if (!$buddy_list_wrapper.length) {
                $buddy_list_wrapper = $("#buddy_list_wrapper");
            }
            ui.update_scrollbar($buddy_list_wrapper);
        },
        group_pms: function () {
            if (!$group_pms.length) {
                $group_pms = $("#group-pms");
            }
            ui.update_scrollbar($group_pms);
        },
    };
}());

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
    return buddy_list.find_li({
        key: user_id,
    });
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

            if (!old_timestamp || old_timestamp < message.timestamp) {
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

function focus_lost() {
    // When we become idle, we don't immediately send anything to the
    // server; instead, we wait for our next periodic update, since
    // this data is fundamentally not timely.
    exports.has_focus = false;
}

exports.redraw_user = function (user_id) {
    if (page_params.realm_presence_disabled) {
        return;
    }

    var filter_text = exports.get_filter_text();

    if (!buddy_data.matches_filter(filter_text, user_id)) {
        return;
    }

    var info = buddy_data.get_item(user_id);

    buddy_list.insert_or_move({
        key: user_id,
        item: info,
    });

    exports.update_scrollbar.users();
};

exports.searching = function () {
    return exports.user_filter && exports.user_filter.searching();
};

exports.build_user_sidebar = function () {
    if (page_params.realm_presence_disabled) {
        return;
    }

    var filter_text = exports.get_filter_text();

    var user_ids = buddy_data.get_filtered_and_sorted_user_ids(filter_text);

    buddy_list.populate({
        keys: user_ids,
    });

    resize.resize_page_components();

    return user_ids; // for testing
};

function do_update_users_for_search() {
    // Hide all the popovers but not userlist sidebar
    // when the user is searching.
    popovers.hide_all_except_userlist_sidebar();
    exports.build_user_sidebar();
    exports.user_cursor.reset();
}

var update_users_for_search = _.throttle(do_update_users_for_search, 50);

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
            href: hash_util.huddle_with_uri(huddle),
            fraction_present: buddy_data.huddle_fraction_present(huddle),
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
    exports.update_scrollbar.group_pms();
};

function focus_ping(want_redraw) {
    if (reload_state.is_in_progress()) {
        blueslip.log("Skipping querying presence because reload in progress");
        return;
    }
    channel.post({
        url: '/json/users/me/presence',
        data: {status: exports.has_focus ? exports.ACTIVE : exports.IDLE,
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
                exports.redraw();
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

    exports.set_cursor_and_filter();

    exports.build_user_sidebar();
    exports.update_huddles();

    buddy_list.start_scroll_handler();

    // Let the server know we're here, but pass "false" for
    // want_redraw, since we just got all this info in page_params.
    focus_ping(false);

    function get_full_presence_list_update() {
        focus_ping(true);
    }

    setInterval(get_full_presence_list_update, ACTIVE_PING_INTERVAL_MS);

    ui.set_up_scrollbar($("#buddy_list_wrapper"));
    ui.set_up_scrollbar($("#group-pms"));
};

exports.update_presence_info = function (email, info, server_time) {
    var user_id = people.get_user_id(email);
    if (!user_id) {
        blueslip.warn('unknown email: ' + email);
        return;
    }

    presence.set_info_for_user(user_id, info, server_time);
    exports.redraw_user(user_id);
    exports.update_huddles();
    pm_list.update_private_messages();
};

exports.on_set_away = function (user_id) {
    user_status.set_away(user_id);
    exports.redraw_user(user_id);
    pm_list.update_private_messages();
};

exports.on_revoke_away = function (user_id) {
    user_status.revoke_away(user_id);
    exports.redraw_user(user_id);
    pm_list.update_private_messages();
};

exports.redraw = function () {
    exports.build_user_sidebar();
    exports.user_cursor.redraw();
    exports.update_huddles();
    pm_list.update_private_messages();
};

exports.reset_users = function () {
    // Call this when we're leaving the search widget.
    exports.build_user_sidebar();
    exports.user_cursor.clear();
};

exports.narrow_for_user = function (opts) {
    var user_id = buddy_list.get_key_from_li({li: opts.li});
    return exports.narrow_for_user_id({user_id: user_id});
};

exports.narrow_for_user_id = function (opts) {
    var person = people.get_person_from_user_id(opts.user_id);
    var email = person.email;

    narrow.by('pm-with', email, {trigger: 'sidebar'});
    exports.user_filter.clear_and_hide_search();
};

function keydown_enter_key() {
    var user_id = exports.user_cursor.get_key();
    if (user_id === undefined) {
        return;
    }

    exports.narrow_for_user_id({user_id: user_id});
    popovers.hide_all();
}

exports.set_cursor_and_filter = function () {
    exports.user_cursor = list_cursor({
        list: buddy_list,
        highlight_class: 'highlighted_user',
    });

    exports.user_filter = user_search({
        update_list: update_users_for_search,
        reset_items: exports.reset_users,
        on_focus: exports.user_cursor.reset,
    });

    var $input = exports.user_filter.input_field();

    $input.on('blur', exports.user_cursor.clear);

    keydown_util.handle({
        elem: $input,
        handlers: {
            enter_key: function () {
                keydown_enter_key();
                return true;
            },
            up_arrow: function () {
                exports.user_cursor.prev();
                return true;
            },
            down_arrow: function () {
                exports.user_cursor.next();
                return true;
            },
        },
    });
};

exports.initiate_search = function () {
    if (exports.user_filter) {
        exports.user_filter.initiate_search();
    }
};

exports.escape_search = function () {
    if (exports.user_filter) {
        exports.user_filter.escape_search();
    }
};

exports.get_filter_text = function () {
    if (!exports.user_filter) {
        // This may be overly defensive, but there may be
        // situations where get called before everything is
        // fully initialized.  The empty string is a fine
        // default here.
        blueslip.warn('get_filter_text() is called before initialization');
        return '';
    }

    return exports.user_filter.text();
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = activity;
}
window.activity = activity;
