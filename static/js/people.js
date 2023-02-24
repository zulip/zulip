import md5 from "blueimp-md5";
import {format, utcToZonedTime} from "date-fns-tz";

import * as typeahead from "../shared/js/typeahead";

import * as blueslip from "./blueslip";
import {FoldDict} from "./fold_dict";
import {$t} from "./i18n";
import * as message_user_ids from "./message_user_ids";
import * as muted_users from "./muted_users";
import {page_params} from "./page_params";
import * as reload_state from "./reload_state";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as util from "./util";

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
export function init() {
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
}

// WE INITIALIZE DATA STRUCTURES HERE!
init();

function split_to_ints(lst) {
    return lst.split(",").map((s) => Number.parseInt(s, 10));
}

export function get_users_from_ids(user_ids) {
    return user_ids.map((user_id) => get_by_user_id(user_id));
}

export function get_by_user_id(user_id, ignore_missing) {
    if (!people_by_user_id_dict.has(user_id) && !ignore_missing) {
        blueslip.error("Unknown user_id in get_by_user_id: " + user_id);
        return undefined;
    }
    return people_by_user_id_dict.get(user_id);
}

export function validate_user_ids(user_ids) {
    const good_ids = [];
    const bad_ids = [];

    for (const user_id of user_ids) {
        if (people_by_user_id_dict.has(user_id)) {
            good_ids.push(user_id);
        } else {
            bad_ids.push(user_id);
        }
    }

    if (bad_ids.length > 0) {
        blueslip.warn(`We have untracked user_ids: ${bad_ids}`);
    }

    return good_ids;
}

export function get_by_email(email) {
    const person = people_dict.get(email);

    if (!person) {
        return undefined;
    }

    if (person.email.toLowerCase() !== email.toLowerCase()) {
        blueslip.warn(
            "Obsolete email passed to get_by_email: " + email + " new email = " + person.email,
        );
    }

    return person;
}

export function get_bot_owner_user(user) {
    const owner_id = user.bot_owner_id;

    if (owner_id === undefined || owner_id === null) {
        // This is probably a cross-realm bot.
        return undefined;
    }

    return get_by_user_id(owner_id);
}

export function can_admin_user(user) {
    return (
        (user.is_bot && user.bot_owner_id && user.bot_owner_id === page_params.user_id) ||
        is_my_user_id(user.user_id)
    );
}

export function id_matches_email_operand(user_id, email) {
    const person = get_by_email(email);

    if (!person) {
        // The user may type bad data into the search bar, so
        // we don't complain too loud here.
        blueslip.debug("User email operand unknown: " + email);
        return false;
    }

    return person.user_id === user_id;
}

export function update_email(user_id, new_email) {
    const person = people_by_user_id_dict.get(user_id);
    person.email = new_email;
    people_dict.set(new_email, person);

    // For legacy reasons we don't delete the old email
    // keys in our dictionaries, so that reverse lookups
    // still work correctly.
}

export function get_visible_email(user) {
    if (user.delivery_email) {
        return user.delivery_email;
    }
    return user.email;
}

export function get_user_id(email) {
    const person = get_by_email(email);
    if (person === undefined) {
        const error_msg = "Unknown email for get_user_id: " + email;
        blueslip.error(error_msg);
        return undefined;
    }
    const user_id = person.user_id;
    if (!user_id) {
        blueslip.error("No user_id found for " + email);
        return undefined;
    }

    return user_id;
}

export function is_known_user_id(user_id) {
    /*
    For certain low-stakes operations, such as emoji reactions,
    we may get a user_id that we don't know about, because the
    user may have been deactivated.  (We eventually want to track
    deactivated users on the client, but until then, this is an
    expedient thing we can check.)
    */
    return people_by_user_id_dict.has(user_id);
}

export function is_known_user(user) {
    return user && is_known_user_id(user.user_id);
}

function sort_numerically(user_ids) {
    user_ids.sort((a, b) => a - b);

    return user_ids;
}

export function huddle_string(message) {
    if (message.type !== "private") {
        return undefined;
    }

    let user_ids = message.display_recipient.map((recip) => recip.id);

    user_ids = user_ids.filter(
        (user_id) => user_id && people_by_user_id_dict.has(user_id) && !is_my_user_id(user_id),
    );

    if (user_ids.length <= 1) {
        return undefined;
    }

    user_ids = sort_numerically(user_ids);

    return user_ids.join(",");
}

export function user_ids_string_to_emails_string(user_ids_string) {
    const user_ids = split_to_ints(user_ids_string);

    let emails = user_ids.map((user_id) => {
        const person = people_by_user_id_dict.get(user_id);
        return person && person.email;
    });

    if (!emails.every(Boolean)) {
        blueslip.warn("Unknown user ids: " + user_ids_string);
        return undefined;
    }

    emails = emails.map((email) => email.toLowerCase());

    emails.sort();

    return emails.join(",");
}

export function user_ids_string_to_ids_array(user_ids_string) {
    const user_ids = user_ids_string.split(",");
    const ids = user_ids.map(Number);
    return ids;
}

export function get_participants_from_user_ids_string(user_ids_string) {
    let user_ids = user_ids_string_to_ids_array(user_ids_string);
    // Convert to set to ensure there are no duplicate ids.
    user_ids = new Set(user_ids);
    // For group PMs or 1:1 private messages, the user_ids_string
    // contains just the other user, so we need to add ourselves if not
    // already present. For PM to self, the current user is already present,
    // in user_ids_string, so we don't need to add it which is take care of
    // by user_ids being a `Set`.
    user_ids.add(my_user_id);
    return user_ids;
}

export function emails_strings_to_user_ids_array(emails_string) {
    const user_ids_string = emails_strings_to_user_ids_string(emails_string);
    if (user_ids_string === undefined) {
        return undefined;
    }

    const user_ids_array = user_ids_string_to_ids_array(user_ids_string);
    return user_ids_array;
}

export function reply_to_to_user_ids_string(emails_string) {
    // This is basically emails_strings_to_user_ids_string
    // without blueslip warnings, since it can be called with
    // invalid data.
    const emails = emails_string.split(",");

    let user_ids = emails.map((email) => {
        const person = get_by_email(email);
        return person && person.user_id;
    });

    if (!user_ids.every(Boolean)) {
        return undefined;
    }

    user_ids = sort_numerically(user_ids);

    return user_ids.join(",");
}

export function emails_to_full_names_string(emails) {
    return emails
        .map((email) => {
            email = email.trim();
            const person = get_by_email(email);
            if (person !== undefined) {
                return person.full_name;
            }
            return email;
        })
        .join(", ");
}

export function get_user_time_preferences(user_id) {
    const user_timezone = get_by_user_id(user_id).timezone;
    if (user_timezone) {
        return settings_data.get_time_preferences(user_timezone);
    }
    return undefined;
}

export function get_user_time(user_id) {
    const user_pref = get_user_time_preferences(user_id);
    if (user_pref) {
        const current_date = utcToZonedTime(new Date(), user_pref.timezone);
        // This could happen if the timezone is invalid.
        if (Number.isNaN(current_date.getTime())) {
            blueslip.error(`Got invalid date for timezone: ${user_pref.timezone}`);
            return undefined;
        }
        return format(current_date, user_pref.format, {timeZone: user_pref.timezone});
    }
    return undefined;
}

export function get_user_type(user_id) {
    const user_profile = get_by_user_id(user_id);

    return settings_config.user_role_map.get(user_profile.role);
}

export function emails_strings_to_user_ids_string(emails_string) {
    const emails = emails_string.split(",");
    return email_list_to_user_ids_string(emails);
}

export function email_list_to_user_ids_string(emails) {
    let user_ids = emails.map((email) => {
        const person = get_by_email(email);
        return person && person.user_id;
    });

    if (!user_ids.every(Boolean)) {
        blueslip.warn("Unknown emails: " + emails);
        return undefined;
    }

    user_ids = sort_numerically(user_ids);

    return user_ids.join(",");
}

export function get_full_names_for_poll_option(user_ids) {
    return get_display_full_names(user_ids).join(", ");
}

function get_display_full_name(user_id) {
    const person = get_by_user_id(user_id);
    if (!person) {
        blueslip.error("Unknown user id " + user_id);
        return "?";
    }

    if (muted_users.is_user_muted(user_id)) {
        return $t({defaultMessage: "Muted user"});
    }

    return person.full_name;
}

export function get_display_full_names(user_ids) {
    return user_ids.map((user_id) => get_display_full_name(user_id));
}

export function get_full_name(user_id) {
    return people_by_user_id_dict.get(user_id).full_name;
}

function _calc_user_and_other_ids(user_ids_string) {
    const user_ids = split_to_ints(user_ids_string);
    const other_ids = user_ids.filter((user_id) => !is_my_user_id(user_id));
    return {user_ids, other_ids};
}

export function get_recipients(user_ids_string) {
    // See message_store.get_pm_full_names() for a similar function.

    const {other_ids} = _calc_user_and_other_ids(user_ids_string);

    if (other_ids.length === 0) {
        // private message with oneself
        return my_full_name();
    }

    const names = get_display_full_names(other_ids).sort();
    return names.join(", ");
}

export function pm_reply_user_string(message) {
    const user_ids = pm_with_user_ids(message);

    if (!user_ids) {
        return undefined;
    }

    return user_ids.join(",");
}

export function pm_reply_to(message) {
    const user_ids = pm_with_user_ids(message);

    if (!user_ids) {
        return undefined;
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
}

function sorted_other_user_ids(user_ids) {
    // This excludes your own user id unless you're the only user
    // (i.e. you sent a message to yourself).

    const other_user_ids = user_ids.filter((user_id) => !is_my_user_id(user_id));

    if (other_user_ids.length >= 1) {
        user_ids = other_user_ids;
    } else {
        user_ids = [my_user_id];
    }

    user_ids = sort_numerically(user_ids);

    return user_ids;
}

export function concat_huddle(user_ids, user_id) {
    /*
        We assume user_ids and user_id have already
        been validated by the caller.

        The only logic we're encapsulating here is
        how to encode huddles.
    */
    const sorted_ids = sort_numerically([...user_ids, user_id]);
    return sorted_ids.join(",");
}

export function pm_lookup_key_from_user_ids(user_ids) {
    /*
        The server will sometimes include our own user id
        in keys for PMs, but we only want our user id if
        we sent a message to ourself.
    */
    user_ids = sorted_other_user_ids(user_ids);
    return user_ids.join(",");
}

export function pm_lookup_key(user_ids_string) {
    const user_ids = split_to_ints(user_ids_string);
    return pm_lookup_key_from_user_ids(user_ids);
}

export function all_user_ids_in_pm(message) {
    if (message.type !== "private") {
        return undefined;
    }

    if (message.display_recipient.length === 0) {
        blueslip.error("Empty recipient list in message");
        return undefined;
    }

    let user_ids = message.display_recipient.map((recip) => recip.id);

    user_ids = sort_numerically(user_ids);
    return user_ids;
}

export function pm_with_user_ids(message) {
    if (message.type !== "private") {
        return undefined;
    }

    if (message.display_recipient.length === 0) {
        blueslip.error("Empty recipient list in message");
        return undefined;
    }

    const user_ids = message.display_recipient.map((recip) => recip.id);

    return sorted_other_user_ids(user_ids);
}

export function group_pm_with_user_ids(message) {
    if (message.type !== "private") {
        return undefined;
    }

    if (message.display_recipient.length === 0) {
        blueslip.error("Empty recipient list in message");
        return undefined;
    }

    const user_ids = message.display_recipient.map((recip) => recip.id);
    const is_user_present = user_ids.some((user_id) => is_my_user_id(user_id));
    if (is_user_present) {
        user_ids.sort();
        if (user_ids.length > 2) {
            return user_ids;
        }
    }
    return false;
}

export function pm_perma_link(message) {
    const user_ids = all_user_ids_in_pm(message);

    if (!user_ids) {
        return undefined;
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
}

export function pm_with_url(message) {
    const user_ids = pm_with_user_ids(message);

    if (!user_ids) {
        return undefined;
    }

    let suffix;

    if (user_ids.length > 1) {
        suffix = "group";
    } else {
        const person = get_by_user_id(user_ids[0]);
        if (person && person.full_name) {
            suffix = person.full_name.replace(/[ "%/<>`\p{C}]+/gu, "-");
        } else {
            blueslip.error("Unknown people in message");
            suffix = "unk";
        }
    }

    const slug = user_ids.join(",") + "-" + suffix;
    const uri = "#narrow/pm-with/" + slug;
    return uri;
}

export function update_email_in_reply_to(reply_to, user_id, new_email) {
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
}

export function pm_with_operand_ids(operand) {
    let emails = operand.split(",");
    emails = emails.map((email) => email.trim());
    let persons = emails.map((email) => people_dict.get(email));

    // If your email is included in a PM group with other people, just ignore it
    if (persons.length > 1) {
        const my_user = people_by_user_id_dict.get(my_user_id);
        persons = persons.filter((person) => person !== my_user);
    }

    if (!persons.every(Boolean)) {
        return undefined;
    }

    let user_ids = persons.map((person) => person.user_id);

    user_ids = sort_numerically(user_ids);

    return user_ids;
}

export function emails_to_slug(emails_string) {
    let slug = reply_to_to_user_ids_string(emails_string);

    if (!slug) {
        return undefined;
    }

    slug += "-";

    const emails = emails_string.split(",");

    if (emails.length === 1) {
        const name = get_by_email(emails[0]).full_name;
        slug += name.replace(/[ "%/<>`\p{C}]+/gu, "-");
    } else {
        slug += "group";
    }

    return slug;
}

export function slug_to_emails(slug) {
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
        user_ids_string = exclude_me_from_string(user_ids_string);
        return user_ids_string_to_emails_string(user_ids_string);
    }
    /* istanbul ignore next */
    return undefined;
}

export function exclude_me_from_string(user_ids_string) {
    // Exclude me from a user_ids_string UNLESS I'm the
    // only one in it.
    let user_ids = split_to_ints(user_ids_string);

    if (user_ids.length <= 1) {
        // We either have a message to ourself, an empty
        // slug, or a message to somebody else where we weren't
        // part of the slug.
        return user_ids.join(",");
    }

    user_ids = user_ids.filter((user_id) => !is_my_user_id(user_id));

    return user_ids.join(",");
}

export function format_small_avatar_url(raw_url) {
    const url = new URL(raw_url, location);
    url.search += (url.search ? "&" : "") + "s=50";
    return url.href;
}

export function sender_is_bot(message) {
    if (message.sender_id) {
        const person = get_by_user_id(message.sender_id);
        return person.is_bot;
    }
    return false;
}

export function sender_is_guest(message) {
    if (message.sender_id) {
        const person = get_by_user_id(message.sender_id);
        return person.is_guest;
    }
    return false;
}

function gravatar_url_for_email(email) {
    const hash = md5(email.toLowerCase());
    const avatar_url = "https://secure.gravatar.com/avatar/" + hash + "?d=identicon";
    const small_avatar_url = format_small_avatar_url(avatar_url);
    return small_avatar_url;
}

export function small_avatar_url_for_person(person) {
    if (person.avatar_url) {
        return format_small_avatar_url(person.avatar_url);
    }

    if (person.avatar_url === null) {
        return gravatar_url_for_email(person.email);
    }

    return format_small_avatar_url("/avatar/" + person.user_id);
}

function medium_gravatar_url_for_email(email) {
    const hash = md5(email.toLowerCase());
    const avatar_url = "https://secure.gravatar.com/avatar/" + hash + "?d=identicon";
    const url = new URL(avatar_url, location);
    url.search += (url.search ? "&" : "") + "s=500";
    return url.href;
}

export function medium_avatar_url_for_person(person) {
    /* Unlike the small avatar URL case, we don't generally have a
     * medium avatar URL included in person objects. So only have the
     * gravatar and server endpoints here. */

    if (person.avatar_url === null) {
        return medium_gravatar_url_for_email(person.email);
    }

    return "/avatar/" + person.user_id + "/medium";
}

export function sender_info_for_recent_topics_row(sender_ids) {
    const senders_info = [];
    for (const id of sender_ids) {
        const sender = {...get_by_user_id(id)};
        sender.avatar_url_small = small_avatar_url_for_person(sender);
        sender.is_muted = muted_users.is_user_muted(id);
        senders_info.push(sender);
    }
    return senders_info;
}

export function small_avatar_url(message) {
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
        // tutorial, where it's ok to fall back to the URL in the fake
        // messages.
        person = get_by_user_id(message.sender_id);
    }

    // The first time we encounter a sender in a message, we may
    // not have person.avatar_url set, but if we do, then use that.
    if (person && person.avatar_url) {
        return small_avatar_url_for_person(person);
    }

    // Try to get info from the message if we didn't have a `person` object
    // or if the avatar was missing. We do this verbosely to avoid false
    // positives on line coverage (we don't do branch checking).
    if (message.avatar_url) {
        return format_small_avatar_url(message.avatar_url);
    }

    if (person && person.avatar_url === undefined) {
        // If we don't have an avatar_url at all, we use `GET
        // /avatar/{user_id}` endpoint to obtain avatar url.  This is
        // required to take advantage of the user_avatar_url_field_optional
        // optimization, which saves a huge amount of network traffic on
        // servers with 10,000s of user accounts.
        return format_small_avatar_url("/avatar/" + person.user_id);
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
}

export function is_valid_email_for_compose(email) {
    if (is_cross_realm_email(email)) {
        return true;
    }

    const person = get_by_email(email);
    if (!person) {
        return false;
    }

    // we allow deactivated users in compose so that
    // one can attempt to reply to threads that contained them.
    return true;
}

export function is_valid_bulk_emails_for_compose(emails) {
    // Returns false if at least one of the emails is invalid.
    return emails.every((email) => {
        if (!is_valid_email_for_compose(email)) {
            return false;
        }
        return true;
    });
}

export function is_active_user_for_popover(user_id) {
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
}

export function filter_all_persons(pred) {
    const ret = [];
    for (const person of people_by_user_id_dict.values()) {
        if (pred(person)) {
            ret.push(person);
        }
    }
    return ret;
}

export function filter_all_users(pred) {
    const ret = [];
    for (const person of active_user_dict.values()) {
        if (pred(person)) {
            ret.push(person);
        }
    }
    return ret;
}

export function get_realm_users() {
    // includes humans and bots from your realm
    return Array.from(active_user_dict.values());
}

export function get_active_human_ids() {
    const human_ids = [];

    for (const user of active_user_dict.values()) {
        if (!user.is_bot) {
            human_ids.push(user.user_id);
        }
    }

    return human_ids;
}

export function get_non_active_human_ids() {
    const human_ids = [];

    for (const user of non_active_user_dict.values()) {
        if (!user.is_bot) {
            human_ids.push(user.user_id);
        }
    }

    return human_ids;
}

export function get_active_human_count() {
    let count = 0;
    for (const person of active_user_dict.values()) {
        if (!person.is_bot) {
            count += 1;
        }
    }
    return count;
}

export function get_active_user_ids() {
    // This includes active users and active bots.
    return Array.from(active_user_dict.keys());
}

export function get_non_active_realm_users() {
    return Array.from(non_active_user_dict.values());
}

export function is_cross_realm_email(email) {
    const person = get_by_email(email);
    if (!person) {
        return undefined;
    }
    return cross_realm_dict.has(person.user_id);
}

export function get_recipient_count(person) {
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
}

export function incr_recipient_count(user_id) {
    const old_count = pm_recipient_count_dict.get(user_id) || 0;
    pm_recipient_count_dict.set(user_id, old_count + 1);
}

export function clear_recipient_counts_for_testing() {
    pm_recipient_count_dict.clear();
}

export function set_recipient_count_for_testing(user_id, count) {
    pm_recipient_count_dict.set(user_id, count);
}

export function get_message_people() {
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
    const message_people = message_user_ids
        .user_ids()
        .map((user_id) => people_by_user_id_dict.get(user_id))
        .filter(Boolean);

    return message_people;
}

export function get_active_message_people() {
    const message_people = get_message_people();
    const active_message_people = message_people.filter((item) =>
        active_user_dict.has(item.user_id),
    );
    return active_message_people;
}

export function get_people_for_search_bar(query) {
    const pred = build_person_matcher(query);

    const message_people = get_message_people();

    const small_results = message_people.filter((item) => pred(item));

    if (small_results.length >= 5) {
        return small_results;
    }

    return filter_all_persons(pred);
}

export function build_termlet_matcher(termlet) {
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
}

export function build_person_matcher(query) {
    query = query.trim();

    const termlets = query.toLowerCase().split(/\s+/);
    const termlet_matchers = termlets.map((termlet) => build_termlet_matcher(termlet));

    return function (user) {
        const email = user.email.toLowerCase();

        if (email.startsWith(query)) {
            return true;
        }

        return termlet_matchers.every((matcher) => matcher(user));
    };
}

export function filter_people_by_search_terms(users, search_terms) {
    const filtered_users = new Map();

    // Build our matchers outside the loop to avoid some
    // search overhead that is not user-specific.
    const matchers = search_terms.map((search_term) => build_person_matcher(search_term));

    // Loop through users and populate filtered_users only
    // if they include search_terms
    for (const user of users) {
        const person = get_by_email(user.email);
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
}

export const is_valid_full_name_and_user_id = (full_name, user_id) => {
    const person = people_by_user_id_dict.get(user_id);

    if (!person) {
        return false;
    }

    return person.full_name === full_name;
};

export const get_actual_name_from_user_id = (user_id) => {
    /*
        If you are dealing with user-entered data, you
        should validate the user_id BEFORE calling
        this function.
    */
    const person = people_by_user_id_dict.get(user_id);

    if (!person) {
        blueslip.error("Unknown user_id: " + user_id);
        return undefined;
    }

    return person.full_name;
};

export function get_user_id_from_name(full_name) {
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
        return undefined;
    }

    if (is_duplicate_full_name(full_name)) {
        return undefined;
    }

    return person.user_id;
}

export function track_duplicate_full_name(full_name, user_id, to_remove) {
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
}

export function is_duplicate_full_name(full_name) {
    const ids = duplicate_full_name_data.get(full_name);

    return ids && ids.size > 1;
}

export function get_mention_syntax(full_name, user_id, silent) {
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
    if (
        (is_duplicate_full_name(full_name) || full_name_matches_wildcard_mention(full_name)) &&
        user_id
    ) {
        mention += "|" + user_id;
    }
    mention += "**";
    return mention;
}

function full_name_matches_wildcard_mention(full_name) {
    return ["all", "everyone", "stream"].includes(full_name);
}

export function _add_user(person) {
    /*
        This is common code to add any user, even
        users who may be deactivated or outside
        our realm (like cross-realm bots).
    */
    person.is_moderator = false;
    if (person.role === settings_config.user_role_values.moderator.code) {
        person.is_moderator = true;
    }
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

    track_duplicate_full_name(person.full_name, person.user_id);
    people_dict.set(person.email, person);
    people_by_name_dict.set(person.full_name, person);
}

export function add_active_user(person) {
    active_user_dict.set(person.user_id, person);
    _add_user(person);
    non_active_user_dict.delete(person.user_id);
}

export const is_person_active = (user_id) => {
    if (!people_by_user_id_dict.has(user_id)) {
        blueslip.error("No user found.", user_id);
    }

    if (cross_realm_dict.has(user_id)) {
        return true;
    }

    return active_user_dict.has(user_id);
};

export function add_cross_realm_user(person) {
    if (!people_dict.has(person.email)) {
        _add_user(person);
    }
    cross_realm_dict.set(person.user_id, person);
}

export function deactivate(person) {
    // We don't fully remove a person from all of our data
    // structures, because deactivated users can be part
    // of somebody's PM list.
    active_user_dict.delete(person.user_id);
    non_active_user_dict.set(person.user_id, person);
}

export function report_late_add(user_id, email) {
    // This function is extracted to make unit testing easier,
    // plus we may fine-tune our reporting here for different
    // types of realms.
    const msg = "Added user late: user_id=" + user_id + " email=" + email;

    if (reload_state.is_in_progress()) {
        blueslip.log(msg);
    } else {
        blueslip.error(msg);
    }
}

export function extract_people_from_message(message) {
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

        report_late_add(user_id, person.email);

        _add_user({
            email: person.email,
            user_id,
            full_name: person.full_name,
            is_admin: person.is_realm_admin || false,
            is_bot: person.is_bot || false,
        });
    }
}

function safe_lower(s) {
    return (s || "").toLowerCase();
}

export function matches_user_settings_search(person, value) {
    const email = settings_data.email_for_user_settings(person);

    return safe_lower(person.full_name).includes(value) || safe_lower(email).includes(value);
}

export function filter_for_user_settings_search(persons, query) {
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
    return persons.filter((person) => matches_user_settings_search(person, query));
}

export function maybe_incr_recipient_count(message) {
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
        incr_recipient_count(user_id);
    }
}

export function set_full_name(person_obj, new_full_name) {
    if (people_by_name_dict.has(person_obj.full_name)) {
        people_by_name_dict.delete(person_obj.full_name);
    }
    // Remove previous and add new full name to the duplicate full name tracker.
    track_duplicate_full_name(person_obj.full_name, person_obj.user_id, true);
    track_duplicate_full_name(new_full_name, person_obj.user_id);
    people_by_name_dict.set(new_full_name, person_obj);
    person_obj.full_name = new_full_name;
}

export function set_custom_profile_field_data(user_id, field) {
    if (field.id === undefined) {
        blueslip.error("Trying to set undefined field id");
        return;
    }
    people_by_user_id_dict.get(user_id).profile_data[field.id] = {
        value: field.value,
        rendered_value: field.rendered_value,
    };
}

export function is_current_user(email) {
    if (email === null || email === undefined || page_params.is_spectator) {
        return false;
    }

    return email.toLowerCase() === my_current_email().toLowerCase();
}

export function initialize_current_user(user_id) {
    my_user_id = user_id;
}

export function my_full_name() {
    return people_by_user_id_dict.get(my_user_id).full_name;
}

export function my_current_email() {
    return people_by_user_id_dict.get(my_user_id).email;
}

export function my_current_user_id() {
    return my_user_id;
}

export function my_custom_profile_data(field_id) {
    if (field_id === undefined) {
        blueslip.error("Undefined field id");
        return undefined;
    }
    return get_custom_profile_data(my_user_id, field_id);
}

export function get_custom_profile_data(user_id, field_id) {
    const profile_data = people_by_user_id_dict.get(user_id).profile_data;
    if (profile_data === undefined) {
        return null;
    }
    return profile_data[field_id];
}

export function is_my_user_id(user_id) {
    if (!user_id) {
        return false;
    }

    if (typeof user_id !== "number") {
        blueslip.error("user_id is a string in my_user_id: " + user_id);
        user_id = Number.parseInt(user_id, 10);
    }

    return user_id === my_user_id;
}

export function compare_by_name(a, b) {
    return util.strcmp(a.full_name, b.full_name);
}

export function sort_but_pin_current_user_on_top(users) {
    const my_user = people_by_user_id_dict.get(my_user_id);
    if (users.includes(my_user)) {
        users.splice(users.indexOf(my_user), 1);
        users.sort(compare_by_name);
        users.unshift(my_user);
    } else {
        users.sort(compare_by_name);
    }
}

export function initialize(my_user_id, params) {
    for (const person of params.realm_users) {
        add_active_user(person);
    }

    for (const person of params.realm_non_active_users) {
        non_active_user_dict.set(person.user_id, person);
        _add_user(person);
    }

    for (const person of params.cross_realm_bots) {
        add_cross_realm_user(person);
    }

    initialize_current_user(my_user_id);
}
