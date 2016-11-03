var people = (function () {

var exports = {};

// The following three Dicts point to the same objects
// All people we've seen
var people_dict = new Dict({fold_case: true});
var people_by_name_dict = new Dict({fold_case: true});
// People in this realm
var realm_people_dict = new Dict({fold_case: true});
var cross_realm_dict = new Dict({fold_case: true});
var pm_recipient_count_dict = new Dict({fold_case: true});

exports.get_by_email = function get_by_email(email) {
    return people_dict.get(email);
};

exports.realm_get = function realm_get(email) {
    return realm_people_dict.get(email);
};

exports.get_all_persons = function () {
    return people_dict.values();
};

exports.get_realm_persons = function () {
    return realm_people_dict.values();
};

exports.is_cross_realm_email = function (email) {
    return cross_realm_dict.has(email);
};

exports.get_recipient_count = function (person) {
    // We can have fake person objects like the "all"
    // pseudo-person in at-mentions.  They will have
    // the pm_recipient_count on the object itself.
    if (person.pm_recipient_count) {
        return person.pm_recipient_count;
    }

    var count = pm_recipient_count_dict.get(person.email);

    return count || 0;
};

exports.incr_recipient_count = function (email) {
    var old_count = pm_recipient_count_dict.get(email) || 0;
    pm_recipient_count_dict.set(email, old_count + 1);
};

exports.filter_people_by_search_terms = function (users, search_terms) {
        var filtered_users = {};

        // Loop through users and populate filtered_users only
        // if they include search_terms
        _.each(users, function (user) {
            var person = exports.get_by_email(user.email);
            // Get person object (and ignore errors)
            if (!person || !person.full_name) {
                return;
            }

            // Remove extra whitespace
            var names = person.full_name.toLowerCase().split(/\s+/);
            names = _.map(names, function (name) {
                return name.trim();
            });

            // Return user emails that include search terms
            return _.any(search_terms, function (search_term) {
                return _.any(names, function (name) {
                    if (name.indexOf(search_term.trim()) === 0) {
                        filtered_users[user.email] = true;
                    }
                });
            });
        });
        return filtered_users;
};

exports.get_by_name = function realm_get(name) {
    return people_by_name_dict.get(name);
};

// TODO: Replace these with the tests setting up page_params before
// loading people.js
exports.test_set_people_dict = function (data) {
    people_dict = new Dict.from(data);
};
exports.test_set_people_name_dict = function (data) {
    people_by_name_dict = new Dict.from(data);
};

function people_cmp(person1, person2) {
    var name_cmp = util.strcmp(person1.full_name, person2.full_name);
    if (name_cmp < 0) {
        return -1;
    } else if (name_cmp > 0) {
        return 1;
    }
    return util.strcmp(person1.email, person2.email);
}

exports.get_rest_of_realm = function get_rest_of_realm() {
    var people_minus_you = [];
    realm_people_dict.each(function (person) {
        if (!util.is_current_user(person.email)) {
            people_minus_you.push({"email": person.email,
                                   "full_name": person.full_name});
        }
    });
    return people_minus_you.sort(people_cmp);
};

exports.add = function add(person) {
    people_dict.set(person.email, person);
    people_by_name_dict.set(person.full_name, person);
};

exports.add_in_realm = function add_in_realm(person) {
    realm_people_dict.set(person.email, person);
    exports.add(person);
};

exports.remove = function remove(person) {
    people_dict.del(person.email);
    people_by_name_dict.del(person.full_name);
    realm_people_dict.del(person.email);
};

exports.reify = function reify(person) {
    // If a locally sent message is a PM to
    // an out-of-realm recipient, a people_dict
    // entry is created with simply an email address
    // Once we've received the full person object, replace
    // it
    if (! people_dict.has(person.email)) {
        return;
    }

    var old_person = people_dict.get(person.email);

    // Only overwrite skeleton objects here.  If the object
    // had already been reified, exit early.
    if (!old_person.skeleton) {
        return;
    }

    var new_person = _.extend({}, old_person, person);
    new_person.skeleton = false;

    people_dict.set(person.email, person);
    people_by_name_dict.set(person.full_name, person);

    if (people_by_name_dict.has(person.email)) {
        people_by_name_dict.del(person.email);
    }
};

exports.update = function update(person) {
    if (! people_dict.has(person.email)) {
        blueslip.error("Got update_person event for unexpected user",
                       {email: person.email});
        return;
    }
    var person_obj = people_dict.get(person.email);

    if (_.has(person, 'full_name')) {
        if (people_by_name_dict.has(person_obj.full_name)) {
            people_by_name_dict.set(person.full_name, person_obj);
            people_by_name_dict.del(person_obj.full_name);
        }

        person_obj.full_name = person.full_name;

        if (util.is_current_user(person.email)) {
            page_params.fullname = person.full_name;
        }
    }

    if (_.has(person, 'is_admin')) {
        person_obj.is_admin = person.is_admin;

        if (util.is_current_user(person.email)) {
            page_params.is_admin = person.is_admin;
            admin.show_or_hide_menu_item();
        }
    }

    if (_.has(person, 'avatar_url')) {
        var url = person.avatar_url + "&y=" + new Date().getTime();
        person_obj.avatar_url = url;

        if (util.is_current_user(person.email)) {
          page_params.avatar_url = url;
          $("#user-settings-avatar").attr("src", url);
        }

        $(".inline_profile_picture.u-" + person.id).css({
          "background-image": "url(" + url + ")"
        });
    }

    activity.set_user_statuses([]);

    // TODO: update sender names on messages
};

$(function () {
    _.each(page_params.people_list, function (person) {
        exports.add_in_realm(person);
    });

    _.each(page_params.cross_realm_bots, function (person) {
        if (!people_dict.has(person.email)) {
            exports.add(person);
        }
        cross_realm_dict.set(person.email, person);
    });

    delete page_params.people_list; // We are the only consumer of this.
    delete page_params.cross_realm_bots;
});

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = people;
}
