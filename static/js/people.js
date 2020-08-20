"use strict";

const md5 = require("blueimp-md5");
const _ = require("lodash");
const moment = require("moment-timezone");

require("unorm"); // String.prototype.normalize polyfill for IE11
const typeahead = require("../shared/js/typeahead");

const FoldDict = require("./fold_dict").FoldDict;
const settings_data = require("./settings_data");
const util = require("./util");

let people_dict;
let people_by_name_dict;
let people_by_user_id_dict;
let active_user_dict;
let non_active_user_dict;
let cross_realm_dict;
let pm_recipient_count_dict;
let duplicate_full_name_data;
let my_user_id;

// We have an init() function so that our automated tests
// can easily clear data.
exports.init = function () {
    // The following three dicts point to the same objects
    // (all people we've seen), but people_dict can have duplicate
    // keys related to email changes.  We want to deprecate
    // people_dict over time and always do lookups by user_id.
    people_dict = new FoldDict();
    people_by_name_dict = new FoldDict();
    people_by_user_id_dict = new Map();

    // The next dictionary includes all active users (human/user)
    // in our realm, but it excludes non-active users and
    // cross-realm bots.
    active_user_dict = new Map();
    non_active_user_dict = new Map();
    cross_realm_dict = new Map(); // keyed by user_id
    pm_recipient_count_dict = new Map();

    // This maintains a set of ids of people with same full names.
    duplicate_full_name_data = new FoldDict();
};

// WE INITIALIZE DATA STRUCTURES HERE!
exports.init();

function split_to_ints(lst) {
    return lst.split(",").map((s) => parseInt(s, 10));
}

exports.get_by_user_id = function (user_id, ignore_missing) {
    if (!people_by_user_id_dict.has(user_id) && !ignore_missing) {
        blueslip.error("Unknown user_id in get_by_user_id: " + user_id);
        return;
    }
    return people_by_user_id_dict.get(user_id);
};

exports.get_by_email = function (email) {
    const person = people_dict.get(email);

    if (!person) {
        return;
    }

    if (person.email.toLowerCase() !== email.toLowerCase()) {
        blueslip.warn(
            "Obsolete email passed to get_by_email: " + email + " new email = " + person.email,
        );
    }

    return person;
};

exports.get_bot_owner_user = function (user) {
    const owner_id = user.bot_owner_id;

    if (owner_id === undefined || owner_id === null) {
        // This is probably a cross-realm bot.
        return;
    }

    return exports.get_by_user_id(owner_id);
};

exports.id_matches_email_operand = function (user_id, email) {
    const person = exports.get_by_email(email);

    if (!person) {
        // The user may type bad data into the search bar, so
        // we don't complain too loud here.
        blueslip.debug("User email operand unknown: " + email);
        return false;
    }

    return person.user_id === user_id;
};

exports.update_email = function (user_id, new_email) {
    const person = people_by_user_id_dict.get(user_id);
    person.email = new_email;
    people_dict.set(new_email, person);

    // For legacy reasons we don't delete the old email
    // keys in our dictionaries, so that reverse lookups
    // still work correctly.
};

exports.get_visible_email = function (user) {
    if (user.delivery_email) {
        return user.delivery_email;
    }
    return user.email;
};

exports.get_user_id = function (email) {
    const person = exports.get_by_email(email);
    if (person === undefined) {
        const error_msg = "Unknown email for get_user_id: " + email;
        blueslip.error(error_msg);
        return;
    }
    const user_id = person.user_id;
    if (!user_id) {
        blueslip.error("No user_id found for " + email);
        return;
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
    user_ids.sort((a, b) => a - b);

    return user_ids;
}

exports.huddle_string = function (message) {
    if (message.type !== "private") {
        return;
    }

    let user_ids = message.display_recipient.map((recip) => recip.id);

    function is_huddle_recip(user_id) {
        return user_id && people_by_user_id_dict.has(user_id) && !exports.is_my_user_id(user_id);
    }

    user_ids = user_ids.filter(is_huddle_recip);

    if (user_ids.length <= 1) {
        return;
    }

    user_ids = sort_numerically(user_ids);

    return user_ids.join(",");
};

exports.user_ids_string_to_emails_string = function (user_ids_string) {
    const user_ids = split_to_ints(user_ids_string);

    let emails = user_ids.map((user_id) => {
        const person = people_by_user_id_dict.get(user_id);
        return person && person.email;
    });

    if (!emails.every(Boolean)) {
        blueslip.warn("Unknown user ids: " + user_ids_string);
        return;
    }

    emails = emails.map((email) => email.toLowerCase());

    emails.sort();

    return emails.join(",");
};

exports.user_ids_string_to_ids_array = function (user_ids_string) {
    const user_ids = user_ids_string.split(",");
    const ids = user_ids.map((id) => Number(id));
    return ids;
};

exports.emails_strings_to_user_ids_array = function (emails_string) {
    const user_ids_string = exports.emails_strings_to_user_ids_string(emails_string);
    if (user_ids_string === undefined) {
        return;
    }

    const user_ids_array = exports.user_ids_string_to_ids_array(user_ids_string);
    return user_ids_array;
};

exports.reply_to_to_user_ids_string = function (emails_string) {
    // This is basically emails_strings_to_user_ids_string
    // without blueslip warnings, since it can be called with
    // invalid data.
    const emails = emails_string.split(",");

    let user_ids = emails.map((email) => {
        const person = exports.get_by_email(email);
        return person && person.user_id;
    });

    if (!user_ids.every(Boolean)) {
        return;
    }

    user_ids = sort_numerically(user_ids);

    return user_ids.join(",");
};

exports.get_user_time_preferences = function (user_id) {
    const user_timezone = exports.get_by_user_id(user_id).timezone;
    if (user_timezone) {
        return settings_data.get_time_preferences(user_timezone);
    }
};

exports.get_user_time = function (user_id) {
    const user_pref = exports.get_user_time_preferences(user_id);
    if (user_pref) {
        return moment().tz(user_pref.timezone).format(user_pref.format);
    }
};

exports.get_user_type = function (user_id) {
    const user_profile = exports.get_by_user_id(user_id);

    if (user_profile.is_owner) {
        return i18n.t("Owner");
    } else if (user_profile.is_admin) {
        return i18n.t("Administrator");
    } else if (user_profile.is_guest) {
        return i18n.t("Guest");
    } else if (user_profile.is_bot) {
        return i18n.t("Bot");
    }
    return i18n.t("Member");
};

exports.emails_strings_to_user_ids_string = function (emails_string) {
    const emails = emails_string.split(",");
    return exports.email_list_to_user_ids_string(emails);
};

exports.email_list_to_user_ids_string = function (emails) {
    let user_ids = emails.map((email) => {
        const person = exports.get_by_email(email);
        return person && person.user_id;
    });

    if (!user_ids.every(Boolean)) {
        blueslip.warn("Unknown emails: " + emails);
        return;
    }

    user_ids = sort_numerically(user_ids);

    return user_ids.join(",");
};

exports.safe_full_names = function (user_ids) {
    let names = user_ids.map((user_id) => {
        const person = people_by_user_id_dict.get(user_id);
        return person && person.full_name;
    });

    names = names.filter(Boolean);

    return names.join(", ");
};

exports.get_full_name = function (user_id) {
    return people_by_user_id_dict.get(user_id).full_name;
};

exports.get_recipients = function (user_ids_string) {
    // See message_store.get_pm_full_names() for a similar function.

    const user_ids = split_to_ints(user_ids_string);
    const other_ids = user_ids.filter((user_id) => !exports.is_my_user_id(user_id));

    if (other_ids.length === 0) {
        // private message with oneself
        return exports.my_full_name();
    }

    const names = other_ids.map(exports.get_full_name).sort();
    return names.join(", ");
};

exports.pm_reply_user_string = function (message) {
    const user_ids = exports.pm_with_user_ids(message);

    if (!user_ids) {
        return;
    }

    return user_ids.join(",");
};

exports.pm_reply_to = function (message) {
    const user_ids = exports.pm_with_user_ids(message);

    if (!user_ids) {
        return;
    }

    const emails = user_ids.map((user_id) => {
        const person = people_by_user_id_dict.get(user_id);
        if (!person) {
            blueslip.error("Unknown user id in message: " + user_id);
            return "?";
        }
        return person.email;
    });

    emails.sort();

    const reply_to = emails.join(",");

    return reply_to;
};

function sorted_other_user_ids(user_ids) {
    // This excludes your own user id unless you're the only user
    // (i.e. you sent a message to yourself).

    const other_user_ids = user_ids.filter((user_id) => !exports.is_my_user_id(user_id));

    if (other_user_ids.length >= 1) {
        user_ids = other_user_ids;
    } else {
        user_ids = [my_user_id];
    }

    user_ids = sort_numerically(user_ids);

    return user_ids;
}

exports.concat_huddle = function (user_ids, user_id) {
    /*
        We assume user_ids and user_id have already
        been validated by the caller.

        The only logic we're encapsulating here is
        how to encode huddles.
    */
    const sorted_ids = sort_numerically([...user_ids, user_id]);
    return sorted_ids.join(",");
};

exports.pm_lookup_key = function (user_ids_string) {
    /*
        The server will sometimes include our own user id
        in keys for PMs, but we only want our user id if
        we sent a message to ourself.
    */
    let user_ids = split_to_ints(user_ids_string);
    user_ids = sorted_other_user_ids(user_ids);
    return user_ids.join(",");
};

exports.all_user_ids_in_pm = function (message) {
    if (message.type !== "private") {
        return;
    }

    if (message.display_recipient.length === 0) {
        blueslip.error("Empty recipient list in message");
        return;
    }

    let user_ids = message.display_recipient.map((recip) => recip.id);

    user_ids = sort_numerically(user_ids);
    return user_ids;
};

exports.pm_with_user_ids = function (message) {
    if (message.type !== "private") {
        return;
    }

    if (message.display_recipient.length === 0) {
        blueslip.error("Empty recipient list in message");
        return;
    }

    const user_ids = message.display_recipient.map((recip) => recip.id);

    return sorted_other_user_ids(user_ids);
};

exports.group_pm_with_user_ids = function (message) {
    if (message.type !== "private") {
        return;
    }

    if (message.display_recipient.length === 0) {
        blueslip.error("Empty recipient list in message");
        return;
    }

    const user_ids = message.display_recipient.map((recip) => recip.id);
    const is_user_present = user_ids.some((user_id) => exports.is_my_user_id(user_id));
    if (is_user_present) {
        user_ids.sort();
        if (user_ids.length > 2) {
            return user_ids;
        }
    }
    return false;
};

exports.pm_perma_link = function (message) {
    const user_ids = exports.all_user_ids_in_pm(message);

    if (!user_ids) {
        return;
    }

    let suffix;

    if (user_ids.length >= 3) {
        suffix = "group";
    } else {
        suffix = "pm";
    }

    const slug = user_ids.join(",") + "-" + suffix;
    const uri = "#narrow/pm-with/" + slug;
    return uri;
};

exports.pm_with_url = function (message) {
    const user_ids = exports.pm_with_user_ids(message);

    if (!user_ids) {
        return;
    }

    let suffix;

    if (user_ids.length > 1) {
        suffix = "group";
    } else {
        const person = exports.get_by_user_id(user_ids[0]);
        if (person && person.email) {
            suffix = person.email.split("@")[0].toLowerCase();
        } else {
            blueslip.error("Unknown people in message");
            suffix = "unk";
        }
    }

    const slug = user_ids.join(",") + "-" + suffix;
    const uri = "#narrow/pm-with/" + slug;
    return uri;
};

exports.update_email_in_reply_to = function (reply_to, user_id, new_email) {
    // We try to replace an old email with a new email in a reply_to,
    // but we try to avoid changing the reply_to if we don't have to,
    // and we don't warn on any errors.
    let emails = reply_to.split(",");

    const persons = emails.map((email) => people_dict.get(email.trim()));

    if (!persons.every(Boolean)) {
        return reply_to;
    }

    const needs_patch = persons.some((person) => person.user_id === user_id);

    if (!needs_patch) {
        return reply_to;
    }

    emails = persons.map((person) => {
        if (person.user_id === user_id) {
            return new_email;
        }
        return person.email;
    });

    return emails.join(",");
};

exports.pm_with_operand_ids = function (operand) {
    let emails = operand.split(",");
    emails = emails.map((email) => email.trim());
    let persons = emails.map((email) => people_dict.get(email));

    // If your email is included in a PM group with other people, just ignore it
    if (persons.length > 1) {
        persons = _.without(persons, people_by_user_id_dict.get(my_user_id));
    }

    if (!persons.every(Boolean)) {
        return;
    }

    let user_ids = persons.map((person) => person.user_id);

    user_ids = sort_numerically(user_ids);

    return user_ids;
};

exports.emails_to_slug = function (emails_string) {
    let slug = exports.reply_to_to_user_ids_string(emails_string);

    if (!slug) {
        return;
    }

    slug += "-";

    const emails = emails_string.split(",");

    if (emails.length === 1) {
        slug += emails[0].split("@")[0].toLowerCase();
    } else {
        slug += "group";
    }

    return slug;
};

exports.slug_to_emails = function (slug) {
    /*
        It's not super important to be flexible about
        PM-related slugs, since you would rarely post
        them to the web, but we we do want to support
        reasonable variations:

            99-alice@example.com
            99

        Our canonical version is 99-alice@example.com,
        and we only care about the "99" prefix.
    */
    const m = /^([\d,]+)(-.*)?/.exec(slug);
    if (m) {
        let user_ids_string = m[1];
        user_ids_string = exports.exclude_me_from_string(user_ids_string);
        return exports.user_ids_string_to_emails_string(user_ids_string);
    }
};

exports.exclude_me_from_string = function (user_ids_string) {
    // Exclude me from a user_ids_string UNLESS I'm the
    // only one in it.
    let user_ids = split_to_ints(user_ids_string);

    if (user_ids.length <= 1) {
        // We either have a message to ourself, an empty
        // slug, or a message to somebody else where we weren't
        // part of the slug.
        return user_ids.join(",");
    }

    user_ids = user_ids.filter((user_id) => !exports.is_my_user_id(user_id));

    return user_ids.join(",");
};

exports.format_small_avatar_url = function (raw_url) {
    const url = raw_url + "&s=50";
    return url;
};

exports.sender_is_bot = function (message) {
    if (message.sender_id) {
        const person = exports.get_by_user_id(message.sender_id);
        return person.is_bot;
    }
    return false;
};

exports.sender_is_guest = function (message) {
    if (message.sender_id) {
        const person = exports.get_by_user_id(message.sender_id);
        return person.is_guest;
    }
    return false;
};

function gravatar_url_for_email(email) {
    const hash = md5(email.toLowerCase());
    const avatar_url = "https://secure.gravatar.com/avatar/" + hash + "?d=identicon";
    const small_avatar_url = exports.format_small_avatar_url(avatar_url);
    return small_avatar_url;
}

exports.small_avatar_url_for_person = function (person) {
    if (person.avatar_url) {
        return exports.format_small_avatar_url(person.avatar_url);
    }

    if (person.avatar_url === null) {
        return gravatar_url_for_email(person.email);
    }

    return exports.format_small_avatar_url("/avatar/" + person.user_id);
};

exports.sender_info_with_small_avatar_urls_for_sender_ids = function (sender_ids) {
    const senders_info = [];
    for (const id of sender_ids) {
        const sender = {...exports.get_by_user_id(id)};
        sender.avatar_url_small = exports.small_avatar_url_for_person(sender);
        senders_info.push(sender);
    }
    return senders_info;
};

exports.small_avatar_url = function (message) {
    // Try to call this function in all places where we need 25px
    // avatar images, so that the browser can help
    // us avoid unnecessary network trips.  (For user-uploaded avatars,
    // the s=25 parameter is essentially ignored, but it's harmless.)
    //
    // We actually request these at s=50, so that we look better
    // on retina displays.

    let person;
    if (message.sender_id) {
        // We should always have message.sender_id, except for in the
        // tutorial, where it's ok to fall back to the url in the fake
        // messages.
        person = exports.get_by_user_id(message.sender_id);
    }

    // The first time we encounter a sender in a message, we may
    // not have person.avatar_url set, but if we do, then use that.
    if (person && person.avatar_url) {
        return exports.small_avatar_url_for_person(person);
    }

    // Try to get info from the message if we didn't have a `person` object
    // or if the avatar was missing. We do this verbosely to avoid false
    // positives on line coverage (we don't do branch checking).
    if (message.avatar_url) {
        return exports.format_small_avatar_url(message.avatar_url);
    }

    if (person && person.avatar_url === undefined) {
        // If we don't have an avatar_url at all, we use `GET
        // /avatar/{user_id}` endpoint to obtain avatar url.  This is
        // required to take advantage of the user_avatar_url_field_optional
        // optimization, which saves a huge amount of network traffic on
        // servers with 10,000s of user accounts.
        return exports.format_small_avatar_url("/avatar/" + person.user_id);
    }

    // For computing the user's email, we first trust the person
    // object since that is updated via our real-time sync system, but
    // if unavailable, we use the sender email.
    let email;
    if (person) {
        email = person.email;
    } else {
        email = message.sender_email;
    }

    return gravatar_url_for_email(email);
};

exports.is_valid_email_for_compose = function (email) {
    if (exports.is_cross_realm_email(email)) {
        return true;
    }

    const person = exports.get_by_email(email);
    if (!person) {
        return false;
    }
    return active_user_dict.has(person.user_id);
};

exports.is_valid_bulk_emails_for_compose = function (emails) {
    // Returns false if at least one of the emails is invalid.
    return emails.every((email) => {
        if (!exports.is_valid_email_for_compose(email)) {
            return false;
        }
        return true;
    });
};

exports.is_active_user_for_popover = function (user_id) {
    // For popover menus, we include cross-realm bots as active
    // users.

    if (cross_realm_dict.get(user_id)) {
        return true;
    }
    if (active_user_dict.has(user_id)) {
        return true;
    }

    // TODO: We can report errors here once we start loading
    //       deactivated users at page-load time. For now just warn.
    if (!people_by_user_id_dict.has(user_id)) {
        blueslip.warn("Unexpectedly invalid user_id in user popover query: " + user_id);
    }

    return false;
};

exports.filter_all_persons = function (pred) {
    const ret = [];
    for (const person of people_by_user_id_dict.values()) {
        if (pred(person)) {
            ret.push(person);
        }
    }
    return ret;
};

exports.filter_all_users = function (pred) {
    const ret = [];
    for (const person of active_user_dict.values()) {
        if (pred(person)) {
            ret.push(person);
        }
    }
    return ret;
};

exports.get_realm_users = function () {
    // includes humans and bots from your realm
    return Array.from(active_user_dict.values());
};

exports.get_active_human_ids = function () {
    const human_ids = [];

    for (const user of active_user_dict.values()) {
        if (!user.is_bot) {
            human_ids.push(user.user_id);
        }
    }

    return human_ids;
};

exports.get_non_active_human_ids = function () {
    const human_ids = [];

    for (const user of non_active_user_dict.values()) {
        if (!user.is_bot) {
            human_ids.push(user.user_id);
        }
    }

    return human_ids;
};

exports.get_active_human_count = function () {
    let count = 0;
    for (const person of active_user_dict.values()) {
        if (!person.is_bot) {
            count += 1;
        }
    }
    return count;
};

exports.get_active_user_ids = function () {
    // This includes active users and active bots.
    return Array.from(active_user_dict.keys());
};

exports.get_non_active_realm_users = function () {
    return Array.from(non_active_user_dict.values());
};

exports.is_cross_realm_email = function (email) {
    const person = exports.get_by_email(email);
    if (!person) {
        return;
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

    /*
        For searching in the search bar, we will
        have true `person` objects with `user_id`.

        Likewise, we'll have user_id if we
        are tab-completing a user to send a PM
        to (but we only get called if we're not
        currently in a stream view).

        Finally, we'll have user_id if we are adding
        people to a stream (w/typeahead).

    */
    const count = pm_recipient_count_dict.get(person.user_id);

    return count || 0;
};

exports.incr_recipient_count = function (user_id) {
    const old_count = pm_recipient_count_dict.get(user_id) || 0;
    pm_recipient_count_dict.set(user_id, old_count + 1);
};

exports.get_message_people = function () {
    /*
        message_people are roughly the people who have
        actually sent messages that are currently
        showing up on your feed.  These people
        are important--we give them preference
        over other users in certain search
        suggestions, since non-message-people are
        presumably either not very active or
        possibly subscribed to streams you don't
        care about.  message_people also includes
        people whom you have sent PMs, but look
        at the message_store code to see the precise
        semantics
    */
    const message_people = message_store
        .user_ids()
        .map((user_id) => people_by_user_id_dict.get(user_id))
        .filter(Boolean);

    return message_people;
};

exports.get_active_message_people = function () {
    const message_people = exports.get_message_people();
    const active_message_people = message_people.filter((item) =>
        active_user_dict.has(item.user_id),
    );
    return active_message_people;
};

exports.get_people_for_search_bar = function (query) {
    const pred = exports.build_person_matcher(query);

    const message_people = exports.get_message_people();

    const small_results = message_people.filter(pred);

    if (small_results.length >= 5) {
        return small_results;
    }

    return exports.filter_all_persons(pred);
};

exports.build_termlet_matcher = function (termlet) {
    termlet = termlet.trim();

    const is_ascii = /^[a-z]+$/.test(termlet);

    return function (user) {
        let full_name = user.full_name;
        if (is_ascii) {
            // Only ignore diacritics if the query is plain ascii
            full_name = typeahead.remove_diacritics(full_name);
        }
        const names = full_name.toLowerCase().split(" ");

        return names.some((name) => name.startsWith(termlet));
    };
};

exports.build_person_matcher = function (query) {
    query = query.trim();

    const termlets = query.toLowerCase().split(/\s+/);
    const termlet_matchers = termlets.map(exports.build_termlet_matcher);

    return function (user) {
        const email = user.email.toLowerCase();

        if (email.startsWith(query)) {
            return true;
        }

        return termlet_matchers.every((matcher) => matcher(user));
    };
};

exports.filter_people_by_search_terms = function (users, search_terms) {
    const filtered_users = new Map();

    // Build our matchers outside the loop to avoid some
    // search overhead that is not user-specific.
    const matchers = search_terms.map((search_term) => exports.build_person_matcher(search_term));

    // Loop through users and populate filtered_users only
    // if they include search_terms
    for (const user of users) {
        const person = exports.get_by_email(user.email);
        // Get person object (and ignore errors)
        if (!person || !person.full_name) {
            continue;
        }

        // Return user emails that include search terms
        const match = matchers.some((matcher) => matcher(user));

        if (match) {
            filtered_users.set(person.user_id, true);
        }
    }

    return filtered_users;
};

exports.is_valid_full_name_and_user_id = (full_name, user_id) => {
    const person = people_by_user_id_dict.get(user_id);

    if (!person) {
        return false;
    }

    return person.full_name === full_name;
};

exports.get_actual_name_from_user_id = (user_id) => {
    /*
        If you are dealing with user-entered data, you
        should validate the user_id BEFORE calling
        this function.
    */
    const person = people_by_user_id_dict.get(user_id);

    if (!person) {
        blueslip.error("Unknown user_id: " + user_id);
        return;
    }

    return person.full_name;
};

exports.get_user_id_from_name = function (full_name) {
    // get_user_id_from_name('Alice Smith') === 42

    /*
        This function is intended to be called
        with a full name that is user-entered, such
        a full name from a user mention.

        We will only return a **unique** user_id
        here.  For duplicate names, our UI should
        force users to disambiguate names with a
        user_id and then call is_valid_full_name_and_user_id
        to make sure the combo is valid.  This is
        exactly what we do with mentions.
    */

    const person = people_by_name_dict.get(full_name);

    if (!person) {
        return;
    }

    if (exports.is_duplicate_full_name(full_name)) {
        return;
    }

    return person.user_id;
};

function people_cmp(person1, person2) {
    const name_cmp = util.strcmp(person1.full_name, person2.full_name);
    if (name_cmp < 0) {
        return -1;
    } else if (name_cmp > 0) {
        return 1;
    }
    return util.strcmp(person1.email, person2.email);
}

exports.get_people_for_stream_create = function () {
    /*
        If you are thinking of reusing this function,
        a better option in most cases is to just
        call `exports.get_realm_users()` and then
        filter out the "me" user yourself as part of
        any other filtering that you are doing.

        In particular, this function does a sort
        that is kinda expensive and may not apply
        to your use case.
    */
    const people_minus_you = [];
    for (const person of active_user_dict.values()) {
        if (!exports.is_my_user_id(person.user_id)) {
            people_minus_you.push({
                email: person.email,
                user_id: person.user_id,
                full_name: person.full_name,
            });
        }
    }
    return people_minus_you.sort(people_cmp);
};

exports.track_duplicate_full_name = function (full_name, user_id, to_remove) {
    let ids;
    if (duplicate_full_name_data.has(full_name)) {
        ids = duplicate_full_name_data.get(full_name);
    } else {
        ids = new Set();
    }
    if (!to_remove && user_id) {
        ids.add(user_id);
    }
    if (to_remove && user_id) {
        ids.delete(user_id);
    }
    duplicate_full_name_data.set(full_name, ids);
};

exports.is_duplicate_full_name = function (full_name) {
    const ids = duplicate_full_name_data.get(full_name);

    return ids && ids.size > 1;
};

exports.get_mention_syntax = function (full_name, user_id, silent) {
    let mention = "";
    if (silent) {
        mention += "@_**";
    } else {
        mention += "@**";
    }
    mention += full_name;
    if (!user_id) {
        blueslip.warn("get_mention_syntax called without user_id.");
    }
    if (exports.is_duplicate_full_name(full_name) && user_id) {
        mention += "|" + user_id;
    }
    mention += "**";
    return mention;
};

exports._add_user = function add(person) {
    /*
        This is common code to add any user, even
        users who may be deactivated or outside
        our realm (like cross-realm bots).
    */
    if (person.user_id) {
        people_by_user_id_dict.set(person.user_id, person);
    } else {
        // We eventually want to lock this down completely
        // and report an error and not update other the data
        // structures here, but we have a lot of edge cases
        // with cross-realm bots, zephyr users, etc., deactivated
        // users, where we are probably fine for now not to
        // find them via user_id lookups.
        blueslip.warn("No user_id provided for " + person.email);
    }

    exports.track_duplicate_full_name(person.full_name, person.user_id);
    people_dict.set(person.email, person);
    people_by_name_dict.set(person.full_name, person);
};

exports.add_active_user = function (person) {
    active_user_dict.set(person.user_id, person);
    exports._add_user(person);
    non_active_user_dict.delete(person.user_id);
};

exports.is_person_active = (user_id) => {
    if (!people_by_user_id_dict.has(user_id)) {
        blueslip.error("No user found.", user_id);
    }

    return active_user_dict.has(user_id);
};

exports.add_cross_realm_user = function (person) {
    if (!people_dict.has(person.email)) {
        exports._add_user(person);
    }
    cross_realm_dict.set(person.user_id, person);
};

exports.deactivate = function (person) {
    // We don't fully remove a person from all of our data
    // structures, because deactivated users can be part
    // of somebody's PM list.
    active_user_dict.delete(person.user_id);
    non_active_user_dict.set(person.user_id, person);
};

exports.report_late_add = function (user_id, email) {
    // This function is extracted to make unit testing easier,
    // plus we may fine-tune our reporting here for different
    // types of realms.
    const msg = "Added user late: user_id=" + user_id + " email=" + email;

    if (reload_state.is_in_progress()) {
        blueslip.log(msg);
    } else {
        blueslip.error(msg);
    }
};

exports.extract_people_from_message = function (message) {
    let involved_people;

    switch (message.type) {
        case "stream":
            involved_people = [
                {
                    full_name: message.sender_full_name,
                    user_id: message.sender_id,
                    email: message.sender_email,
                },
            ];
            break;

        case "private":
            involved_people = message.display_recipient;
            break;

        default:
            involved_people = [];
    }

    // Add new people involved in this message to the people list
    for (const person of involved_people) {
        if (person.unknown_local_echo_user) {
            continue;
        }

        const user_id = person.user_id || person.id;

        if (people_by_user_id_dict.has(user_id)) {
            continue;
        }

        exports.report_late_add(user_id, person.email);

        exports._add_user({
            email: person.email,
            user_id,
            full_name: person.full_name,
            is_admin: person.is_realm_admin || false,
            is_bot: person.is_bot || false,
        });
    }
};

function safe_lower(s) {
    return (s || "").toLowerCase();
}

exports.matches_user_settings_search = function (person, value) {
    const email = settings_data.email_for_user_settings(person);

    return safe_lower(person.full_name).includes(value) || safe_lower(email).includes(value);
};

exports.filter_for_user_settings_search = function (persons, query) {
    /*
        TODO: For large realms, we can optimize this a couple
              different ways.  For realms that don't show
              emails, we can make a simpler filter predicate
              that works solely with full names.  And we can
              also consider two-pass filters that try more
              stingy criteria first, such as exact prefix
              matches, before widening the search.

              See #13554 for more context.
    */
    return persons.filter((person) => exports.matches_user_settings_search(person, query));
};

exports.maybe_incr_recipient_count = function (message) {
    if (message.type !== "private") {
        return;
    }

    if (!message.sent_by_me) {
        return;
    }

    // Track the number of PMs we've sent to this person to improve autocomplete
    for (const recip of message.display_recipient) {
        if (recip.unknown_local_echo_user) {
            continue;
        }

        const user_id = recip.id;
        exports.incr_recipient_count(user_id);
    }
};

exports.set_full_name = function (person_obj, new_full_name) {
    if (people_by_name_dict.has(person_obj.full_name)) {
        people_by_name_dict.delete(person_obj.full_name);
    }
    // Remove previous and add new full name to the duplicate full name tracker.
    exports.track_duplicate_full_name(person_obj.full_name, person_obj.user_id, true);
    exports.track_duplicate_full_name(new_full_name, person_obj.user_id);
    people_by_name_dict.set(new_full_name, person_obj);
    person_obj.full_name = new_full_name;
};

exports.set_custom_profile_field_data = function (user_id, field) {
    if (field.id === undefined) {
        blueslip.error("Trying to set undefined field id");
        return;
    }
    people_by_user_id_dict.get(user_id).profile_data[field.id] = {
        value: field.value,
        rendered_value: field.rendered_value,
    };
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

exports.my_custom_profile_data = function (field_id) {
    if (field_id === undefined) {
        blueslip.error("Undefined field id");
        return;
    }
    return exports.get_custom_profile_data(my_user_id, field_id);
};

exports.get_custom_profile_data = function (user_id, field_id) {
    const profile_data = people_by_user_id_dict.get(user_id).profile_data;
    if (profile_data === undefined) {
        return null;
    }
    return profile_data[field_id];
};

exports.is_my_user_id = function (user_id) {
    if (!user_id) {
        return false;
    }

    if (typeof user_id !== "number") {
        blueslip.error("user_id is a string in my_user_id: " + user_id);
        user_id = parseInt(user_id, 10);
    }

    return user_id === my_user_id;
};

exports.initialize = function (my_user_id, params) {
    for (const person of params.realm_users) {
        exports.add_active_user(person);
    }

    for (const person of params.realm_non_active_users) {
        non_active_user_dict.set(person.user_id, person);
        exports._add_user(person);
    }

    for (const person of params.cross_realm_bots) {
        exports.add_cross_realm_user(person);
    }

    exports.initialize_current_user(my_user_id);
};
