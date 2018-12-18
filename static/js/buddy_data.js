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

function level(user_id) {
    if (people.is_my_user_id(user_id)) {
        // Always put current user at the top.
        return 0;
    }

    var status = presence.get_status(user_id);

    switch (status) {
    case 'active':
        return 1;
    case 'idle':
        return 2;
    default:
        return 3;
    }
}

exports.compare_function = function (a, b) {
    var level_a = level(a);
    var level_b = level(b);
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

exports.info_for = function (user_id) {
    var status = presence.get_status(user_id);
    var person = people.get_person_from_user_id(user_id);

    return {
        href: hash_util.pm_with_uri(person.email),
        name: person.full_name,
        user_id: user_id,
        is_current_user: people.is_my_user_id(user_id),
        num_unread: get_num_unread(user_id),
        type: status,
        type_desc: presence_descriptions[status],
    };
};

exports.get_item = function (user_id) {
    var info = exports.info_for(user_id);
    compose_fade.update_user_info([info], fade_config);
    return info;
};

function user_is_recently_active(user_id) {
    // return true if the user has a green/orange cirle
    return level(user_id) <= 2;
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
