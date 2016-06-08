var people = (function () {

var exports = {};

// The following three Dicts point to the same objects
// All people we've seen
var people_dict = new Dict({fold_case: true});
var people_by_name_dict = new Dict({fold_case: true});
// People in this realm
var realm_people_dict = new Dict({fold_case: true});

exports.get_by_email = function get_by_email(email) {
    return people_dict.get(email);
};

exports.realm_get = function realm_get(email) {
    return realm_people_dict.get(email);
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
    // Compares objects of the form used in people_list.
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
    page_params.people_list.push(person);
    people_dict.set(person.email, person);
    people_by_name_dict.set(person.full_name, person);
    person.pm_recipient_count = 0;
};

exports.add_in_realm = function add_in_realm(person) {
    realm_people_dict.set(person.email, person);
    exports.add(person);
};

exports.remove = function remove(person) {
    var i;
    for (i = 0; i < page_params.people_list.length; i++) {
        if (page_params.people_list[i].email.toLowerCase() === person.email.toLowerCase()) {
            page_params.people_list.splice(i, 1);
            break;
        }
    }
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

    var old_idx = page_params.people_list.indexOf(old_person);

    var new_person = _.extend({}, old_person, person);
    new_person.skeleton = false;

    people_dict.set(person.email, person);
    people_by_name_dict.set(person.full_name, person);
    page_params.people_list[old_idx] = new_person;

    if (people_by_name_dict.has(person.email)) {
        people_by_name_dict.del(person.email);
    }
};

exports.update = function update(person) {
    // Currently the only attribute that can change is full_name, so
    // we just push out changes to that field.  As we add more things
    // that can change, this will need to either get complicated or be
    // replaced by MVC
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

    activity.set_user_statuses([]);

    // TODO: update sender names on messages
};

$(function () {
    _.each(page_params.people_list, function (person) {
        people_dict.set(person.email, person);
        people_by_name_dict.set(person.full_name, person);
        realm_people_dict.set(person.email, person);
        person.pm_recipient_count = 0;
    });

    // The special account feedback@zulip.com is used for in-app
    // feedback and should always show up as an autocomplete option.
    if (! people.get_by_email('feedback@zulip.com')) {
        exports.add({"email": "feedback@zulip.com",
                     "full_name": "Zulip Feedback Bot"});
    }
});

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = people;
}
