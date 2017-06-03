var people = (function () {

var exports = {};

var people_dict;
var people_by_name_dict;
var people_by_user_id_dict;
var realm_people_dict;
var cross_realm_dict;
var pm_recipient_count_dict;
var my_user_id;

// We have an init() function so that our automated tests
// can easily clear data.
exports.init = function () {
    // The following three Dicts point to the same objects
    // (all people we've seen), but people_dict can have duplicate
    // keys related to email changes.  We want to deprecate
    // people_dict over time and always do lookups by user_id.
    people_dict = new Dict({fold_case: true});
    people_by_name_dict = new Dict({fold_case: true});
    people_by_user_id_dict = new Dict();

    realm_people_dict = new Dict();
    cross_realm_dict = new Dict(); // keyed by user_id
    pm_recipient_count_dict = new Dict();
};

// WE INITIALIZE DATA STRUCTURES HERE!
exports.init();

exports.get_person_from_user_id = function (user_id) {
    if (!people_by_user_id_dict.has(user_id)) {
        blueslip.error('Unknown user_id in get_person_from_user_id: ' + user_id);
        return undefined;
    }
    return people_by_user_id_dict.get(user_id);
};

exports.get_by_email = function (email) {
    var person = people_dict.get(email);

    if (!person) {
        return undefined;
    }

    if (person.email.toLowerCase() !== email.toLowerCase()) {
        blueslip.warn(
            'Obsolete email passed to get_by_email: ' + email +
            ' new email = ' + person.email
        );
    }

    return person;
};

exports.get_realm_count = function () {
    // This returns the number of active people in our realm.  It should
    // exclude bots and deactivated users.
    return realm_people_dict.num_items();
};

exports.id_matches_email_operand = function (user_id, email) {
    var person = exports.get_by_email(email);

    if (!person) {
        // The user may type bad data into the search bar, so
        // we don't complain too loud here.
        blueslip.debug('User email operand unknown: ' + email);
        return false;
    }

    return (person.user_id === user_id);
};

exports.update_email = function (user_id, new_email) {
    var person = people_by_user_id_dict.get(user_id);
    person.email = new_email;
    people_dict.set(new_email, person);

    // For legacy reasons we don't delete the old email
    // keys in our dictionaries, so that reverse lookups
    // still work correctly.
};

exports.get_user_id = function (email) {
    var person = people.get_by_email(email);
    if (person === undefined) {
        var error_msg = 'Unknown email for get_user_id: ' + email;
        blueslip.error(error_msg);
        return undefined;
    }
    var user_id = person.user_id;
    if (!user_id) {
        blueslip.error('No userid found for ' + email);
        return undefined;
    }

    return user_id;
};

exports.is_known_user_id = function (user_id) {
    /*
    For certain low-stakes operations, such as emoji reactions,
    we may get a user_id that we don't know about, because the
    user may have been deactivated.  (We eventually want to track
    deactivated users on the client, but until then, this is an
    expedient thing we can check.)
    */
    return people_by_user_id_dict.has(user_id);
};

function sort_numerically(user_ids) {
    user_ids = _.map(user_ids, function (user_id) {
        return parseInt(user_id, 10);
    });

    user_ids.sort(function (a, b) {
        return a - b;
    });

    return user_ids;
}

exports.huddle_string = function (message) {
    if (message.type !== 'private') {
        return;
    }

    var user_ids = _.map(message.display_recipient, function (recip) {
        return recip.id;
    });

    function is_huddle_recip(user_id) {
        return user_id &&
            people_by_user_id_dict.has(user_id) &&
            (!exports.is_my_user_id(user_id));
    }

    user_ids = _.filter(user_ids, is_huddle_recip);

    if (user_ids.length <= 1) {
        return;
    }

    user_ids = sort_numerically(user_ids);

    return user_ids.join(',');
};

exports.user_ids_string_to_emails_string = function (user_ids_string) {
    var user_ids = user_ids_string.split(',');
    var emails = _.map(user_ids, function (user_id) {
        var person = people_by_user_id_dict.get(user_id);
        if (person) {
            return person.email;
        }
    });

    if (!_.all(emails)) {
        blueslip.error('Unknown user ids: ' + user_ids_string);
        return;
    }

    emails = _.map(emails, function (email) {
        return email.toLowerCase();
    });

    emails.sort();

    return emails.join(',');
};

exports.reply_to_to_user_ids_string = function (emails_string) {
    // This is basically emails_strings_to_user_ids_string
    // without blueslip warnings, since it can be called with
    // invalid data.
    var emails = emails_string.split(',');

    var user_ids = _.map(emails, function (email) {
        var person = people.get_by_email(email);
        if (person) {
            return person.user_id;
        }
    });

    if (!_.all(user_ids)) {
        return;
    }

    user_ids = sort_numerically(user_ids);

    return user_ids.join(',');
};

exports.get_user_time_preferences = function (user_id) {
    var user_timezone = people.get_person_from_user_id(user_id).timezone;
    if (user_timezone) {
        if (page_params.twenty_four_hour_time) {
            return {
                timezone: user_timezone,
                format: "HH:mm",
            };
        }
        return {
            timezone: user_timezone,
            format: "hh:mm A",
        };
    }
};

exports.get_user_time = function (user_id) {
    var user_pref = people.get_user_time_preferences(user_id);
    if (user_pref) {
        return moment().tz(user_pref.timezone).format(user_pref.format);
    }
};

exports.emails_strings_to_user_ids_string = function (emails_string) {
    var emails = emails_string.split(',');
    return exports.email_list_to_user_ids_string(emails);
};

exports.email_list_to_user_ids_string = function (emails) {
    var user_ids = _.map(emails, function (email) {
        var person = people.get_by_email(email);
        if (person) {
            return person.user_id;
        }
    });

    if (!_.all(user_ids)) {
        blueslip.warn('Unknown emails: ' + emails);
        return;
    }

    user_ids = sort_numerically(user_ids);

    return user_ids.join(',');
};

exports.get_full_name = function (user_id) {
    return people_by_user_id_dict.get(user_id).full_name;
};

exports.get_recipients = function (user_ids_string) {
    // See message_store.get_pm_full_names() for a similar function.

    var user_ids = user_ids_string.split(',');
    var other_ids = _.reject(user_ids, exports.is_my_user_id);

    if (other_ids.length === 0) {
        // private message with oneself
        return exports.my_full_name();
    }

    var names = _.map(other_ids, exports.get_full_name).sort();
    return names.join(', ');
};

exports.pm_reply_user_string = function (message) {
    var user_ids = people.pm_with_user_ids(message);

    if (!user_ids) {
        return;
    }

    return user_ids.join(',');
};

exports.pm_reply_to = function (message) {
    var user_ids = people.pm_with_user_ids(message);

    if (!user_ids) {
        return;
    }

    var emails = _.map(user_ids, function (user_id) {
        var person = people_by_user_id_dict.get(user_id);
        if (!person) {
            blueslip.error('Unknown user id in message: ' + user_id);
            return '?';
        }
        return person.email;
    });

    emails.sort();

    var reply_to = emails.join(',');

    return reply_to;
};

function sorted_other_user_ids(user_ids) {
    // This excludes your own user id unless you're the only user
    // (i.e. you sent a message to yourself).

    var other_user_ids = _.filter(user_ids, function (user_id) {
        return !people.is_my_user_id(user_id);
    });

    if (other_user_ids.length >= 1) {
        user_ids = other_user_ids;
    } else {
        user_ids = [my_user_id];
    }

    user_ids = sort_numerically(user_ids);

    return user_ids;
}

exports.pm_lookup_key = function (user_ids_string) {
    /*
        The server will sometimes include our own user id
        in keys for PMs, but we only want our user id if
        we sent a message to ourself.
    */
    var user_ids = user_ids_string.split(',');
    user_ids = sorted_other_user_ids(user_ids);
    return user_ids.join(',');
};

exports.pm_with_user_ids = function (message) {
    if (message.type !== 'private') {
        return;
    }

    if (message.display_recipient.length === 0) {
        blueslip.error('Empty recipient list in message');
        return;
    }

    var user_ids = _.map(message.display_recipient, function (elem) {
        return elem.user_id || elem.id;
    });

    return sorted_other_user_ids(user_ids);
};

exports.group_pm_with_user_ids = function (message) {
    if (message.type !== 'private') {
        return;
    }

    if (message.display_recipient.length === 0) {
        blueslip.error('Empty recipient list in message');
        return;
    }
    var user_ids = _.map(message.display_recipient, function (elem) {
        return elem.user_id || elem.id;
    });
    var is_user_present = _.some(user_ids, function (user_id) {
        return people.is_my_user_id(user_id);
    });
    if (is_user_present) {
        user_ids.sort();
        if (user_ids.length > 2) {
            return user_ids;
        }
    }
    return false;
};

exports.pm_with_url = function (message) {
    var user_ids = exports.pm_with_user_ids(message);

    if (!user_ids) {
        return;
    }

    var suffix;

    if (user_ids.length > 1) {
        suffix = 'group';
    } else {
        var person = exports.get_person_from_user_id(user_ids[0]);
        if (person && person.email) {
            suffix = person.email.split('@')[0].toLowerCase();
        } else {
            blueslip.error('Unknown people in message');
            suffix = 'unk';
        }
    }

    var slug = user_ids.join(',') + '-' + suffix;
    var uri = "#narrow/pm-with/" + slug;
    return uri;
};

exports.update_email_in_reply_to = function (reply_to, user_id, new_email) {
    // We try to replace an old email with a new email in a reply_to,
    // but we try to avoid changing the reply_to if we don't have to,
    // and we don't warn on any errors.
    var emails = reply_to.split(',');

    var persons = _.map(emails, function (email) {
        return people_dict.get(email.trim());
    });

    if (!_.all(persons)) {
        return reply_to;
    }

    var needs_patch = _.any(persons, function (person) {
        return person.user_id === user_id;
    });

    if (!needs_patch) {
        return reply_to;
    }

    emails = _.map(persons, function (person) {
        if (person.user_id === user_id) {
            return new_email;
        }
        return person.email;
    });

    return emails.join(',');
};

exports.pm_with_operand_ids = function (operand) {
    var emails = operand.split(',');
    emails = _.map(emails, function (email) { return email.trim(); });
    var persons = _.map(emails, function (email) {
        return people_dict.get(email);
    });

    // If your email is included in a PM group with other people, just ignore it
    if (persons.length > 1) {
        persons = _.without(persons, people_by_user_id_dict.get(my_user_id));
    }

    if (!_.all(persons)) {
        return;
    }

    var user_ids = _.map(persons, function (person) {
        return person.user_id;
    });

    user_ids = sort_numerically(user_ids);

    return user_ids;
};

exports.emails_to_slug = function (emails_string) {
    var slug = exports.emails_strings_to_user_ids_string(emails_string);

    if (!slug) {
        return;
    }

    slug += '-';

    var emails = emails_string.split(',');

    if (emails.length === 1) {
        slug += emails[0].split('@')[0].toLowerCase();
    } else {
        slug += 'group';
    }

    return slug;
};

exports.slug_to_emails = function (slug) {
    var m = /^([\d,]+)-/.exec(slug);
    if (m) {
        var user_ids = m[1];
        return exports.user_ids_string_to_emails_string(user_ids);
    }
};

exports.format_small_avatar_url = function (raw_url) {
    var url = raw_url + "&s=50";
    return url;
};

exports.sender_is_bot = function (message) {
    if (message.sender_id) {
        var person = exports.get_person_from_user_id(message.sender_id);
        return person.is_bot;
    }
    return false;
};

exports.small_avatar_url = function (message) {
    // Try to call this function in all places where we need 25px
    // avatar images, so that the browser can help
    // us avoid unnecessary network trips.  (For user-uploaded avatars,
    // the s=25 parameter is essentially ignored, but it's harmless.)
    //
    // We actually request these at s=50, so that we look better
    // on retina displays.

    var url = "";
    var person;

    if (message.sender_id) {
        // We should always have message.sender_id, except for in the
        // tutorial, where it's ok to fall back to the url in the fake
        // messages.
        person = exports.get_person_from_user_id(message.sender_id);
    }

    // The first time we encounter a sender in a message, we may
    // not have person.avatar_url set, but if we do, then use that.
    if (person && person.avatar_url) {
        url = person.avatar_url;
    } else if (message.avatar_url) {
        // Here we fall back to using the avatar_url from the message
        // itself.
        url = message.avatar_url;
    }

    if (url) {
        url = exports.format_small_avatar_url(url);
    }

    return url;
};

exports.realm_get = function realm_get(email) {
    var person = people.get_by_email(email);
    if (!person) {
        return undefined;
    }
    return realm_people_dict.get(person.user_id);
};

exports.get_all_persons = function () {
    return people_by_user_id_dict.values();
};

exports.get_realm_persons = function () {
    return realm_people_dict.values();
};

exports.is_cross_realm_email = function (email) {
    var person = people.get_by_email(email);
    if (!person) {
        return undefined;
    }
    return cross_realm_dict.has(person.user_id);
};

exports.get_recipient_count = function (person) {
    // We can have fake person objects like the "all"
    // pseudo-person in at-mentions.  They will have
    // the pm_recipient_count on the object itself.
    if (person.pm_recipient_count) {
        return person.pm_recipient_count;
    }

    var user_id = person.user_id || person.id;
    var count = pm_recipient_count_dict.get(user_id);

    return count || 0;
};

exports.incr_recipient_count = function (user_id) {
    var old_count = pm_recipient_count_dict.get(user_id) || 0;
    pm_recipient_count_dict.set(user_id, old_count + 1);
};

// Diacritic removal from:
// https://stackoverflow.com/questions/18236208/perform-a-find-match-with-javascript-ignoring-special-language-characters-acce
function remove_diacritics(s) {
    if (/^[a-z]+$/.test(s)) {
        return s;
    }

    return s
            .replace(/[áàãâä]/g,"a")
            .replace(/[éèëê]/g,"e")
            .replace(/[íìïî]/g,"i")
            .replace(/[óòöôõ]/g,"o")
            .replace(/[úùüû]/g, "u")
            .replace(/[ç]/g, "c")
            .replace(/[ñ]/g, "n");
}

exports.person_matches_query = function (user, query) {
    var email = user.email.toLowerCase();
    var names = user.full_name.toLowerCase().split(' ');

    var termlets = query.toLowerCase().split(/\s+/);
    termlets = _.map(termlets, function (termlet) {
        return termlet.trim();
    });

    if (email.indexOf(query.trim()) === 0) {
        return true;
    }
    return _.all(termlets, function (termlet) {
        var is_ascii = /^[a-z]+$/.test(termlet);
        return _.any(names, function (name) {
            if (is_ascii) {
                // Only ignore diacritics if the query is plain ascii
                name = remove_diacritics(name);
            }
            if (name.indexOf(termlet) === 0) {
                return true;
            }
        });
    });
};

exports.filter_people_by_search_terms = function (users, search_terms) {
        var filtered_users = new Dict();

        // Loop through users and populate filtered_users only
        // if they include search_terms
        _.each(users, function (user) {
            var person = exports.get_by_email(user.email);
            // Get person object (and ignore errors)
            if (!person || !person.full_name) {
                return;
            }

            // Return user emails that include search terms
            var match = _.any(search_terms, function (search_term) {
                return exports.person_matches_query(user, search_term);
            });

            if (match) {
                filtered_users.set(person.user_id, true);
            }
        });
        return filtered_users;
};

exports.get_by_name = function realm_get(name) {
    return people_by_name_dict.get(name);
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
        if (!exports.is_current_user(person.email)) {
            people_minus_you.push({email: person.email,
                                   user_id: person.user_id,
                                   full_name: person.full_name});
        }
    });
    return people_minus_you.sort(people_cmp);
};

exports.add = function add(person) {
    if (person.user_id) {
        people_by_user_id_dict.set(person.user_id, person);
    } else {
        // We eventually want to lock this down completely
        // and report an error and not update other the data
        // structures here, but we have a lot of edge cases
        // with cross-realm bots, zephyr users, etc., deactivated
        // users, where we are probably fine for now not to
        // find them via user_id lookups.
        blueslip.warn('No user_id provided for ' + person.email);
    }

    people_dict.set(person.email, person);
    people_by_name_dict.set(person.full_name, person);
};

exports.add_in_realm = function (person) {
    realm_people_dict.set(person.user_id, person);
    exports.add(person);
};

exports.deactivate = function (person) {
    // We don't fully remove a person from all of our data
    // structures, because deactivated users can be part
    // of somebody's PM list.
    realm_people_dict.del(person.user_id);
};

exports.extract_people_from_message = function (message) {
    var involved_people;

    switch (message.type) {
    case 'stream':
        involved_people = [{full_name: message.sender_full_name,
                            user_id: message.sender_id,
                            email: message.sender_email}];
        break;

    case 'private':
        involved_people = message.display_recipient;
        break;
    }

    // Add new people involved in this message to the people list
    _.each(involved_people, function (person) {
        if (!person.unknown_local_echo_user) {

            var user_id = person.user_id || person.id;

            if (!people_by_user_id_dict.has(user_id)) {
                exports.add({
                    email: person.email,
                    user_id: user_id,
                    full_name: person.full_name,
                    is_admin: person.is_realm_admin || false,
                    is_bot: person.is_bot || false,
                });
            }

            if (message.type === 'private' && message.sent_by_me) {
                // Track the number of PMs we've sent to this person to improve autocomplete
                exports.incr_recipient_count(user_id);
            }
        }
    });
};

exports.set_full_name = function (person_obj, new_full_name) {
    if (people_by_name_dict.has(person_obj.full_name)) {
        people_by_name_dict.del(person_obj.full_name);
    }
    people_by_name_dict.set(new_full_name, person_obj);
    person_obj.full_name = new_full_name;
};

exports.is_current_user = function (email) {
    if (email === null || email === undefined) {
        return false;
    }

    return email.toLowerCase() === exports.my_current_email().toLowerCase();
};

exports.initialize_current_user = function (user_id) {
    my_user_id = user_id;
};

exports.my_full_name = function () {
    return people_by_user_id_dict.get(my_user_id).full_name;
};

exports.my_current_email = function () {
    return people_by_user_id_dict.get(my_user_id).email;
};

exports.my_current_user_id = function () {
    return my_user_id;
};

exports.is_my_user_id = function (user_id) {
    if (!user_id) {
        return false;
    }
    return user_id.toString() === my_user_id.toString();
};

exports.initialize = function () {
    _.each(page_params.realm_users, function (person) {
        exports.add_in_realm(person);
    });

    _.each(page_params.cross_realm_bots, function (person) {
        if (!people_dict.has(person.email)) {
            exports.add(person);
        }
        cross_realm_dict.set(person.user_id, person);
    });

    exports.initialize_current_user(page_params.user_id);

    delete page_params.realm_users; // We are the only consumer of this.
    delete page_params.cross_realm_bots;
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = people;
}
