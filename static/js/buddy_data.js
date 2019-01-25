var buddy_data = (function () {

var exports = {};

/*

   This is the main model code for building the buddy list.
   We also rely on presence.js to compute the actual presence
   for users.  We glue in other "people" data and do
   filtering/sorting of the data that we'll send into the view.

*/

exports.max_size_before_shrinking = 600;

var presence_descriptions = {
    away_me: 'is away',
    away_them: 'is away',
    active: 'is active',
    idle: 'is not active',
};

var fade_config = {
    get_user_id: function (item) {
        return item.user_id;
    },
    fade: function (item) {
        item.faded = true;
    },
    unfade: function (item) {
        item.faded = false;
    },
};

exports.level = function (user_id) {
    if (people.is_my_user_id(user_id)) {
        // Always put current user at the top.
        return 0;
    }

    var status = exports.buddy_status(user_id);

    switch (status) {
    case 'active':
        return 1;
    case 'idle':
        return 2;
    case 'away_them':
        return 3;
    default:
        return 3;
    }
};

exports.buddy_status = function (user_id) {
    if (user_status.is_away(user_id)) {
        if (people.is_my_user_id(user_id)) {
            return 'away_me';
        }

        return 'away_them';
    }

    // get active/idle/etc.
    return presence.get_status(user_id);
};

exports.compare_function = function (a, b) {
    var level_a = exports.level(a);
    var level_b = exports.level(b);
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
};

exports.sort_users = function (user_ids) {
    // TODO sort by unread count first, once we support that
    user_ids.sort(exports.compare_function);
    return user_ids;
};

function filter_user_ids(filter_text, user_ids) {
    if (filter_text === '') {
        return user_ids;
    }

    user_ids = _.reject(user_ids, people.is_my_user_id);

    var search_terms = filter_text.toLowerCase().split(",");
    search_terms = _.map(search_terms, function (s) {
        return s.trim();
    });

    var persons = _.map(user_ids, function (user_id) {
        return people.get_person_from_user_id(user_id);
    });

    var user_id_dict = people.filter_people_by_search_terms(persons, search_terms);
    return user_id_dict.keys();
}

exports.matches_filter = function (filter_text, user_id) {
    // This is a roundabout way of checking a user if you look
    // too hard at it, but it should be fine for now.
    return filter_user_ids(filter_text, [user_id]).length === 1;
};

function get_num_unread(user_id) {
    if (unread.suppress_unread_counts) {
        return 0;
    }
    return unread.num_unread_for_person(user_id);
}

exports.my_user_status = function (user_id) {
    if (!people.is_my_user_id(user_id)) {
        return;
    }

    if (user_status.is_away(user_id)) {
        return i18n.t('(away)');
    }

    return i18n.t('(you)');
};

exports.user_title = function (user_id) {
    var buddy_status = exports.buddy_status(user_id);
    var type_desc = presence_descriptions[buddy_status];
    var status_text = user_status.get_status_text(user_id);
    var person = people.get_person_from_user_id(user_id);
    var title;

    if (status_text) {
        // The user-set status, like "out to lunch",
        // is more important than actual presence.
        title = status_text;
    } else {
        title = person.full_name;
        if (type_desc) {
            // example: "Cordelia Lear is away"
            title += ' ' + type_desc;
        }
    }

    return title;
};

exports.info_for = function (user_id) {
    var buddy_status = exports.buddy_status(user_id);
    var person = people.get_person_from_user_id(user_id);
    var my_user_status = exports.my_user_status(user_id);
    var title = exports.user_title(user_id);

    return {
        href: hash_util.pm_with_uri(person.email),
        name: person.full_name,
        user_id: user_id,
        my_user_status: my_user_status,
        is_current_user: people.is_my_user_id(user_id),
        num_unread: get_num_unread(user_id),
        type: buddy_status,
        title: title,
    };
};

exports.get_item = function (user_id) {
    var info = exports.info_for(user_id);
    compose_fade.update_user_info([info], fade_config);
    return info;
};

function user_is_recently_active(user_id) {
    // return true if the user has a green/orange cirle
    return exports.level(user_id) <= 2;
}

function maybe_shrink_list(user_ids, filter_text) {
    if (user_ids.length <= exports.max_size_before_shrinking) {
        return user_ids;
    }

    if (filter_text) {
        // If the user types something, we want to show all
        // users matching the text, even if they have not been
        // online recently.
        // For super common letters like "s", we may
        // eventually want to filter down to only users that
        // are in presence.get_user_ids().
        return user_ids;
    }

    user_ids = _.filter(user_ids, user_is_recently_active);

    return user_ids;
}

exports.get_filtered_and_sorted_user_ids = function (filter_text) {
    var user_ids;

    if (filter_text) {
        // If there's a filter, select from all users, not just those
        // recently active.
        user_ids = filter_user_ids(filter_text, people.get_active_user_ids());
    } else {
        // From large realms, the user_ids in presence may exclude
        // users who have been idle more than three weeks.  When the
        // filter text is blank, we show only those recently active users.
        user_ids = presence.get_user_ids();
    }

    user_ids = _.filter(user_ids, function (user_id) {
        var person = people.get_person_from_user_id(user_id);

        if (person) {
            // if the user is bot, do not show in presence data.
            if (person.is_bot) {
                return false;
            }
        }
        return true;
    });


    user_ids = maybe_shrink_list(user_ids, filter_text);

    return exports.sort_users(user_ids);
};

exports.get_items_for_users = function (user_ids) {
    var user_info = _.map(user_ids, exports.info_for).filter(function (person) {
        // filtered bots and yourself are set to "undefined" in the `info_for`
        // function.
        return typeof person !== "undefined";
    });

    compose_fade.update_user_info(user_info, fade_config);

    return user_info;
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = buddy_data;
}
window.buddy_data = buddy_data;
