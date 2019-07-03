import md5 from 'blueimp-md5';
import _ from 'underscore';
import { Message, Recipient, FakePerson } from './data_structures';
import { Dict } from './dict';

/** For function argument only */
type UserId = number | string;

interface ProfileEntry {
    value: string;
    rendered_value?: string;
}
interface Person {
    user_id: number;
    avatar_url?: string;
    date_joined?: string;
    email: string;
    full_name: string;
    is_admin?: boolean;
    is_realm_admin?: boolean;
    is_bot?: boolean;
    is_guest?: boolean;
    profile_data?: {
        [id: number]: ProfileEntry;
    };
    timezone?: string;
}

var people_dict: Dict<Person['email'], Person>;
var people_by_name_dict: Dict<Person['full_name'], Person>;
var people_by_user_id_dict: Dict<Person['user_id'], Person>;
var active_user_dict: Dict<Person['user_id'], Person>;
var cross_realm_dict: Dict<Person['user_id'], Person>;
var pm_recipient_count_dict: Dict<Person['user_id'], number>;
var duplicate_full_name_data: Dict<Person['full_name'], Dict<Person['user_id'], undefined>>;
var my_user_id: UserId;

// We have an init() function so that our automated tests
// can easily clear data.
export const init = function (): void {
    // The following three Dicts point to the same objects
    // (all people we've seen), but people_dict can have duplicate
    // keys related to email changes.  We want to deprecate
    // people_dict over time and always do lookups by user_id.
    people_dict = new Dict({fold_case: true});
    people_by_name_dict = new Dict({fold_case: true});
    people_by_user_id_dict = new Dict();

    // The next dictionary includes all active users (human/user)
    // in our realm, but it excludes non-active users and
    // cross-realm bots.
    active_user_dict = new Dict();
    cross_realm_dict = new Dict();
    pm_recipient_count_dict = new Dict();

    // The next Dict maintains a set of ids of people with same full names.
    duplicate_full_name_data = new Dict({fold_case: true});
};

// We initialize data structures the first time people.ts is imported.
init();

export const get_person_from_user_id = function (user_id: UserId): Person | undefined {
    if (!people_by_user_id_dict.has(user_id)) {
        blueslip.error('Unknown user_id in get_person_from_user_id: ' + user_id);
        return undefined;
    }
    return people_by_user_id_dict.get(user_id);
};

export const get_by_email = function (email: Person['email']): Person | undefined {
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

export const get_realm_count = function (): number {
    // This returns the number of active people in our realm.  It should
    // exclude bots and deactivated users.
    return active_user_dict.num_items();
};

export const id_matches_email_operand = function (user_id: UserId, email: Person['email']): boolean {
    var person = get_by_email(email);

    if (!person) {
        // The user may type bad data into the search bar, so
        // we don't complain too loud here.
        blueslip.debug('User email operand unknown: ' + email);
        return false;
    }

    return person.user_id === user_id;
};

export const update_email = function (user_id: UserId, new_email: Person['email']): void {
    var person = people_by_user_id_dict.get(user_id);
    person.email = new_email;
    people_dict.set(new_email, person);

    // For legacy reasons we don't delete the old email
    // keys in our dictionaries, so that reverse lookups
    // still work correctly.
};

export const get_user_id = function (email: Person['email']): UserId | undefined {
    var person = get_by_email(email);
    if (person === undefined) {
        var error_msg = 'Unknown email for get_user_id: ' + email;
        blueslip.error(error_msg);
        return undefined;
    }
    var user_id = person.user_id;
    if (!user_id) {
        blueslip.error('No user_id found for ' + email);
        return undefined;
    }

    return user_id;
};

export const is_known_user_id = function (user_id: UserId): boolean {
    /*
    For certain low-stakes operations, such as emoji reactions,
    we may get a user_id that we don't know about, because the
    user may have been deactivated.  (We eventually want to track
    deactivated users on the client, but until then, this is an
    expedient thing we can check.)
    */
    return people_by_user_id_dict.has(user_id);
};

function sort_numerically(user_ids: UserId[]): Person['user_id'][] {
    var numerical_user_ids = _.map(user_ids, function (user_id: UserId) {
        return Number(user_id);
    });

    numerical_user_ids.sort(function (a, b) {
        return a - b;
    });

    return numerical_user_ids;
}

export const huddle_string = function (message: Message): string | undefined {
    if (message.type !== 'private') {
        return undefined;
    }

    var user_ids = _.map(message.display_recipient, function (recip) {
        return recip.id;
    });

    function is_huddle_recip(user_id: UserId): boolean {
        return user_id &&
            people_by_user_id_dict.has(user_id) &&
            !is_my_user_id(user_id);
    }

    user_ids = _.filter(user_ids, is_huddle_recip);

    if (user_ids.length <= 1) {
        return undefined;
    }

    user_ids = sort_numerically(user_ids);

    return user_ids.join(',');
};

export const user_ids_string_to_emails_string = function (
    user_ids_string: string
): string | undefined {
    var user_ids = user_ids_string.split(',');
    var emails = _.map(user_ids, function (user_id) {
        var person = people_by_user_id_dict.get(user_id);
        return person ? person.email : undefined;
    });

    if (!_.all(emails)) {
        blueslip.warn('Unknown user ids: ' + user_ids_string);
        return undefined;
    }

    emails = _.map(emails, function (email) {
        return email.toLowerCase();
    });

    emails.sort();

    return emails.join(',');
};

export const user_ids_string_to_ids_array = function (user_ids_string: string): Person['user_id'][] {
    var user_ids = user_ids_string.split(',');
    var ids = _.map(user_ids, function (id) {
        return Number(id);
    });
    return ids;
};

export const emails_strings_to_user_ids_array = function (
    emails_string: string
): Person['user_id'][] | undefined {
    var user_ids_string = emails_strings_to_user_ids_string(emails_string);
    if (user_ids_string === undefined) {
        return undefined;
    }

    var user_ids_array = user_ids_string_to_ids_array(user_ids_string);
    return user_ids_array;
};

export const reply_to_to_user_ids_string = function (emails_string: string): string | undefined {
    // This is basically emails_strings_to_user_ids_string
    // without blueslip warnings, since it can be called with
    // invalid data.
    var emails = emails_string.split(',');

    var user_ids = _.map(emails, function (email) {
        var person = get_by_email(email);
        return person ? person.user_id : undefined;
    });

    if (!_.all(user_ids)) {
        return undefined;
    }

    user_ids = sort_numerically(user_ids);

    return user_ids.join(',');
};

export const get_user_time_preferences = function (
    user_id: UserId
): { timezone: string; format: string } | undefined {
    var user_timezone = get_person_from_user_id(user_id).timezone;
    if (user_timezone) {
        if (page_params.twenty_four_hour_time) {
            return {
                timezone: user_timezone,
                format: "H:mm",
            };
        }
        return {
            timezone: user_timezone,
            format: "h:mm A",
        };
    }
    return undefined;
};

export const get_user_time = function (user_id: UserId): string | undefined {
    var user_pref = get_user_time_preferences(user_id);
    return user_pref ?
        moment().tz(user_pref.timezone).format(user_pref.format) : undefined;
};

export const get_user_type = function (user_id: UserId): string {
    var user_profile = get_person_from_user_id(user_id);

    if (user_profile.is_admin) {
        return i18n.t("Administrator");
    } else if (user_profile.is_guest) {
        return i18n.t("Guest");
    } else if (user_profile.is_bot) {
        return i18n.t("Bot");
    }
    return i18n.t("Member");
};

export const emails_strings_to_user_ids_string = function (emails_string: string): string {
    var emails = emails_string.split(',');
    return email_list_to_user_ids_string(emails);
};

export const email_list_to_user_ids_string = function (emails: Person['email'][]): string | undefined {
    var user_ids = _.map(emails, function (email) {
        var person = get_by_email(email);
        return person ? person.user_id : undefined;
    });

    if (!_.all(user_ids)) {
        blueslip.warn('Unknown emails: ' + emails);
        return undefined;
    }

    user_ids = sort_numerically(user_ids);

    return user_ids.join(',');
};

export const safe_full_names = function (user_ids: UserId[]): string {
    var names = _.map(user_ids, function (user_id) {
        var person = people_by_user_id_dict.get(user_id);
        return person ? person.full_name : undefined;
    });

    names = _.filter(names, Boolean);

    return names.join(', ');
};

export const get_full_name = function (user_id: UserId): Person['full_name'] {
    return people_by_user_id_dict.get(user_id).full_name;
};

export const get_recipients = function (user_ids_string: string): string {
    // See message_store.get_pm_full_names() for a similar function.

    var user_ids = user_ids_string.split(',');
    var other_ids = _.reject(user_ids, is_my_user_id);

    if (other_ids.length === 0) {
        // private message with oneself
        return my_full_name();
    }

    var names = _.map(other_ids, get_full_name).sort();
    return names.join(', ');
};

export const pm_reply_user_string = function (message: Message): string | undefined {
    var user_ids = pm_with_user_ids(message);
    return user_ids ? user_ids.join(',') : undefined;
};

export const pm_reply_to = function (message: Message): string | undefined {
    var user_ids = pm_with_user_ids(message);

    if (!user_ids) {
        return undefined;
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

function sorted_other_user_ids(user_ids: UserId[]): Person['user_id'][] {
    // This excludes your own user id unless you're the only user
    // (i.e. you sent a message to yourself).

    var other_user_ids = _.filter(user_ids, function (user_id) {
        return !is_my_user_id(user_id);
    });

    if (other_user_ids.length >= 1) {
        user_ids = other_user_ids;
    } else {
        user_ids = [my_user_id];
    }

    return sort_numerically(user_ids);
}

export const pm_lookup_key = function (user_ids_string: string): string {
    /*
        The server will sometimes include our own user id
        in keys for PMs, but we only want our user id if
        we sent a message to ourself.
    */
    var user_ids = user_ids_string.split(',');
    return sorted_other_user_ids(user_ids).join(',');
};

export const all_user_ids_in_pm = function (message: Message): Person['user_id'][] | undefined {
    if (message.type !== 'private') {
        return undefined;
    }

    if (message.display_recipient.length === 0) {
        blueslip.error('Empty recipient list in message');
        return undefined;
    }

    var user_ids = _.map(message.display_recipient, function (elem) {
        return elem.user_id || elem.id;
    });

    user_ids = sort_numerically(user_ids);
    return user_ids;
};

export const pm_with_user_ids = function (message: Message): Person['user_id'][] | undefined {
    if (message.type !== 'private') {
        return undefined;
    }

    if (message.display_recipient.length === 0) {
        blueslip.error('Empty recipient list in message');
        return undefined;
    }

    var user_ids = _.map(message.display_recipient, function (elem) {
        return elem.user_id || elem.id;
    });

    return sorted_other_user_ids(user_ids);
};

export const group_pm_with_user_ids = function (
    message: Message
): Person['user_id'][] | false | undefined {
    if (message.type !== 'private') {
        return undefined;
    }

    if (message.display_recipient.length === 0) {
        blueslip.error('Empty recipient list in message');
        return undefined;
    }
    var user_ids = _.map(message.display_recipient, function (elem) {
        return elem.user_id || elem.id;
    });
    var is_user_present = _.some(user_ids, function (user_id) {
        return is_my_user_id(user_id);
    });
    if (is_user_present) {
        user_ids.sort();
        if (user_ids.length > 2) {
            return user_ids;
        }
    }
    return false;
};

export const pm_perma_link = function (message: Message): string | undefined {
    var user_ids = all_user_ids_in_pm(message);

    if (!user_ids) {
        return undefined;
    }

    var suffix;

    if (user_ids.length >= 3) {
        suffix = 'group';
    } else {
        suffix = 'pm';
    }

    var slug = user_ids.join(',') + '-' + suffix;
    var uri = "#narrow/pm-with/" + slug;
    return uri;
};

export const pm_with_url = function (message: Message): string | undefined {
    var user_ids = pm_with_user_ids(message);

    if (!user_ids) {
        return undefined;
    }

    var suffix;

    if (user_ids.length > 1) {
        suffix = 'group';
    } else {
        var person = get_person_from_user_id(user_ids[0]);
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

export const update_email_in_reply_to = function (
    reply_to: string,
    user_id: UserId,
    new_email: Person['email']
): string {
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

export const pm_with_operand_ids = function (operand: string): Person['user_id'][] {
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
        return undefined;
    }

    var user_ids = _.map(persons, function (person) {
        return person.user_id;
    });

    user_ids = sort_numerically(user_ids);

    return user_ids;
};

export const emails_to_slug = function (emails_string: string): string | undefined {
    var slug = reply_to_to_user_ids_string(emails_string);

    if (!slug) {
        return undefined;
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

export const slug_to_emails = function (slug: string): string | undefined {
    var m = /^([\d,]+)-/.exec(slug);
    if (m) {
        var user_ids_string = m[1];
        user_ids_string = exclude_me_from_string(user_ids_string);
        return user_ids_string_to_emails_string(user_ids_string);
    }
    return undefined;
};

export const exclude_me_from_string = function (user_ids_string: string): string {
    // Exclude me from a user_ids_string UNLESS I'm the
    // only one in it.
    var user_ids = user_ids_string.split(',');

    if (user_ids.length <= 1) {
        // We either have a message to ourself, an empty
        // slug, or a message to somebody else where we weren't
        // part of the slug.
        return user_ids.join(',');
    }

    user_ids = _.reject(user_ids, is_my_user_id);

    return user_ids.join(',');
};

export const format_small_avatar_url = function (raw_url: string): string {
    var url = raw_url + "&s=50";
    return url;
};

export const sender_is_bot = function (message: Message): boolean {
    if (message.sender_id) {
        var person = get_person_from_user_id(message.sender_id);
        return person.is_bot;
    }
    return false;
};

export const sender_is_guest = function (message: Message): boolean {
    if (message.sender_id) {
        var person = get_person_from_user_id(message.sender_id);
        return person.is_guest;
    }
    return false;
};

function gravatar_url_for_email(email: Person['email']): string {
    var hash = md5(email.toLowerCase());
    var avatar_url = 'https://secure.gravatar.com/avatar/' + hash + '?d=identicon';
    var small_avatar_url = format_small_avatar_url(avatar_url);
    return small_avatar_url;
}

export const small_avatar_url_for_person = function (person: Person): string {
    if (person.avatar_url) {
        return format_small_avatar_url(person.avatar_url);
    }
    return gravatar_url_for_email(person.email);
};

export const small_avatar_url = function (message: Message): string {
    // Try to call this function in all places where we need 25px
    // avatar images, so that the browser can help
    // us avoid unnecessary network trips.  (For user-uploaded avatars,
    // the s=25 parameter is essentially ignored, but it's harmless.)
    //
    // We actually request these at s=50, so that we look better
    // on retina displays.

    var person;
    if (message.sender_id) {
        // We should always have message.sender_id, except for in the
        // tutorial, where it's ok to fall back to the url in the fake
        // messages.
        person = get_person_from_user_id(message.sender_id);
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

    // For computing the user's email, we first trust the person
    // object since that is updated via our real-time sync system, but
    // if unavailable, we use the sender email.
    var email;
    if (person) {
        email = person.email;
    } else {
        email = message.sender_email;
    }

    return gravatar_url_for_email(email);
};

export const is_valid_email_for_compose = function (email: Person['email']): boolean {
    if (is_cross_realm_email(email)) {
        return true;
    }

    var person = get_by_email(email);
    if (!person) {
        return false;
    }
    return active_user_dict.has(person.user_id);
};

export const is_valid_bulk_emails_for_compose = function (emails: Person['email'][]): boolean {
    // Returns false if at least one of the emails is invalid.
    return _.every(emails, function (email) {
        if (!is_valid_email_for_compose(email)) {
            return false;
        }
        return true;
    });
};

export const get_active_user_for_email = function (email: Person['email']): Person | undefined {
    var person = get_by_email(email);
    if (!person) {
        return undefined;
    }
    return active_user_dict.get(person.user_id);
};

export const is_active_user_for_popover = function (user_id: UserId): boolean {
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

export const get_all_persons = function (): Person[] {
    return people_by_user_id_dict.values();
};

export const get_realm_persons = function (): Person[] {
    return active_user_dict.values();
};

export const get_active_human_persons = function (): Person[] {
    var human_persons = get_realm_persons().filter(function (person)  {
        return !person.is_bot;
    });
    return human_persons;
};

export const get_active_user_ids = function (): Person['user_id'][] {
    // This includes active users and active bots.
    return active_user_dict.keys();
};

export const is_cross_realm_email = function (email: Person['email']): boolean | undefined {
    var person = get_by_email(email);
    return person ? cross_realm_dict.has(person.user_id) : undefined;
};

export const get_recipient_count = function (person: Recipient | FakePerson): number {
    // We can have fake person objects like the "all"
    // pseudo-person in at-mentions.  They will have
    // the pm_recipient_count on the object itself.
    const is_fake_person = (person: Recipient | FakePerson): person is FakePerson => {
        return (person as FakePerson).pm_recipient_count !== undefined;
    };

    if (is_fake_person(person)) {
        return person.pm_recipient_count;
    }

    var user_id = person.user_id || person.id;
    var count = pm_recipient_count_dict.get(user_id);

    return count || 0;
};

export const incr_recipient_count = function (user_id: UserId): void {
    var old_count = pm_recipient_count_dict.get(user_id) || 0;
    pm_recipient_count_dict.set(user_id as number, old_count + 1);
};

// Diacritic removal from:
// https://stackoverflow.com/questions/18236208/perform-a-find-match-with-javascript-ignoring-special-language-characters-acce
export const remove_diacritics = function (s: string): string {
    if (/^[a-z]+$/.test(s)) {
        return s;
    }

    return s.replace(/[áàãâä]/g, "a")
        .replace(/[éèëê]/g, "e")
        .replace(/[íìïî]/g, "i")
        .replace(/[óòöôõ]/g, "o")
        .replace(/[úùüû]/g, "u")
        .replace(/[ç]/g, "c")
        .replace(/[ñ]/g, "n");
};

export const person_matches_query = function (user: Person, query: string): boolean {
    var email = user.email.toLowerCase();
    var names = user.full_name.toLowerCase().split(' ');

    var termlets = query.toLowerCase().split(/\s+/);
    termlets = _.map(termlets, function (termlet) {
        return termlet.trim();
    });

    if (email.startsWith(query.trim())) {
        return true;
    }
    return _.all(termlets, function (termlet) {
        var is_ascii = /^[a-z]+$/.test(termlet);
        return _.any(names, function (name) {
            if (is_ascii) {
                // Only ignore diacritics if the query is plain ascii
                name = remove_diacritics(name);
            }
            return name.startsWith(termlet);
        });
    });
};

export const filter_people_by_search_terms = function (
    users: Person[],
    search_terms: string[]
): Dict<Person['user_id'], true> {
    var filtered_users: Dict<Person['user_id'], true> = new Dict();

    // Loop through users and populate filtered_users only
    // if they include search_terms
    _.each(users, function (user) {
        var person = get_by_email(user.email);
        // Get person object (and ignore errors)
        if (!person || !person.full_name) {
            return;
        }

        // Return user emails that include search terms
        var match = _.any(search_terms, function (search_term) {
            return person_matches_query(user, search_term);
        });

        if (match) {
            filtered_users.set(person.user_id, true);
        }
    });
    return filtered_users;
};

export const get_by_name = function (name: Person['full_name']): Person {
    return people_by_name_dict.get(name);
};

type SimplePerson = Pick<Person, "email" | "user_id" | "full_name">;

function people_cmp(person1: SimplePerson, person2: SimplePerson): -1 | 0 | 1 {
    var name_cmp = util.strcmp(person1.full_name, person2.full_name);
    if (name_cmp < 0) {
        return -1;
    } else if (name_cmp > 0) {
        return 1;
    }
    return util.strcmp(person1.email, person2.email);
}

export const get_rest_of_realm = function (): SimplePerson[] {
    var people_minus_you: SimplePerson[] = [];
    active_user_dict.each(function (person) {
        if (!is_current_user(person.email)) {
            people_minus_you.push({
                email: person.email,
                user_id: person.user_id,
                full_name: person.full_name,
            });
        }
    });
    return people_minus_you.sort(people_cmp);
};

export const track_duplicate_full_name = function (
    full_name: Person['full_name'],
    user_id: Person['user_id'],
    to_remove?: boolean
): void {
    var ids: Dict<Person['user_id'], undefined> = new Dict();
    if (duplicate_full_name_data.has(full_name)) {
        ids = duplicate_full_name_data.get(full_name);
    }
    if (!to_remove && user_id) {
        ids.set(user_id, undefined);
    }
    if (to_remove && user_id && ids.has(user_id)) {
        ids.del(user_id);
    }
    duplicate_full_name_data.set(full_name, ids);
};

export const is_duplicate_full_name = function (full_name: Person['full_name']): boolean {
    if (duplicate_full_name_data.has(full_name)) {
        return duplicate_full_name_data.get(full_name).keys().length > 1;
    }
    return false;
};

export const get_mention_syntax = function (
    full_name: Person['full_name'],
    user_id: UserId,
    silent: boolean
): string {
    var mention = '';
    if (silent) {
        mention += '@_**';
    } else {
        mention += '@**';
    }
    mention += full_name;
    if (!user_id) {
        blueslip.warn('get_mention_syntax called without user_id.');
    }
    if (is_duplicate_full_name(full_name) && user_id) {
        mention += '|' + user_id;
    }
    mention += '**';
    return mention;
};

export const add = function (person: Person): void {
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

    track_duplicate_full_name(person.full_name, person.user_id);
    people_dict.set(person.email, person);
    people_by_name_dict.set(person.full_name, person);
};

export const add_in_realm = function (person: Person): void {
    active_user_dict.set(person.user_id, person);
    add(person);
};

export const deactivate = function (person: Person): void {
    // We don't fully remove a person from all of our data
    // structures, because deactivated users can be part
    // of somebody's PM list.
    active_user_dict.del(person.user_id);
};

export const report_late_add = function (user_id: UserId, email: Person['email']): void {
    // This function is extracted to make unit testing easier,
    // plus we may fine-tune our reporting here for different
    // types of realms.
    var msg = 'Added user late: user_id=' + user_id + ' email=' + email;

    if (reload_state.is_in_progress()) {
        blueslip.log(msg);
    } else {
        blueslip.error(msg);
    }
};

export const extract_people_from_message = function (message: Message): void {
    let involved_people: (Person | Recipient)[];

    switch (message.type) {
        case 'stream':
            involved_people = [{
                full_name: message.sender_full_name,
                user_id: message.sender_id,
                email: message.sender_email,
            }];
            break;

        case 'private':
            involved_people = message.display_recipient;
            break;
    }

    const is_unknown_user = (person: Person | Recipient): boolean => {
        return (person as Recipient).unknown_local_echo_user;
    };

    // Add new people involved in this message to the people list
    _.each(involved_people, function (person) {
        if (is_unknown_user(person)) {
            return;
        }

        var user_id = person.user_id || (person as Recipient).id;

        if (people_by_user_id_dict.has(user_id)) {
            return;
        }

        report_late_add(user_id, person.email);

        add({
            email: person.email,
            user_id: user_id,
            full_name: person.full_name,
            is_admin: (person as Person).is_realm_admin || false,
            is_bot: (person as Person).is_bot || false,
        });
    });
};

export const maybe_incr_recipient_count = function (message: Message): void {
    if (message.type !== 'private') {
        return;
    }

    if (!message.sent_by_me) {
        return;
    }

    // Track the number of PMs we've sent to this person to improve autocomplete
    _.each(message.display_recipient, function (person) {

        if (person.unknown_local_echo_user) {
            return;
        }

        var user_id = person.user_id || person.id;
        incr_recipient_count(user_id);
    });
};

export const set_full_name = function (person_obj: Person, new_full_name: Person['full_name']): void {
    if (people_by_name_dict.has(person_obj.full_name)) {
        people_by_name_dict.del(person_obj.full_name);
    }
    // Remove previous and add new full name to the duplicate full name tracker.
    track_duplicate_full_name(person_obj.full_name, person_obj.user_id, true);
    track_duplicate_full_name(new_full_name, person_obj.user_id);
    people_by_name_dict.set(new_full_name, person_obj);
    person_obj.full_name = new_full_name;
};

export const set_custom_profile_field_data = function (
    user_id: UserId,
    field: ProfileEntry & { id: number }
): void {
    if (field.id === undefined) {
        blueslip.error("Unknown field id " + field.id);
        return;
    }
    people_by_user_id_dict.get(user_id).profile_data[field.id] = {
        value: field.value,
        rendered_value: field.rendered_value,
    };
};

export const is_current_user = function (email: Person['email']): boolean {
    if (email === null || email === undefined) {
        return false;
    }

    return email.toLowerCase() === my_current_email().toLowerCase();
};

export const initialize_current_user = function (user_id: UserId): void {
    my_user_id = user_id;
};

export const my_full_name = function (): Person['full_name'] {
    return people_by_user_id_dict.get(my_user_id).full_name;
};

export const my_current_email = function (): Person['email'] {
    return people_by_user_id_dict.get(my_user_id).email;
};

export const my_current_user_id = function (): Person['user_id'] {
    return Number(my_user_id);
};

export const my_custom_profile_data = function (field_id?: number): ProfileEntry | undefined {
    if (field_id === undefined) {
        blueslip.error("Undefined field id");
        return undefined;
    }
    return get_custom_profile_data(my_user_id, field_id);
};

export const get_custom_profile_data = function (
    user_id: UserId,
    field_id: number
): ProfileEntry | null {
    var profile_data = people_by_user_id_dict.get(user_id).profile_data;
    if (profile_data === undefined) {
        return null;
    }
    return profile_data[field_id];
};

export const is_my_user_id = function (user_id: UserId): boolean {
    if (!user_id) {
        return false;
    }
    return user_id.toString() === my_user_id.toString();
};

export const initialize = function (): void {
    _.each(page_params.realm_users, function (person: Person) {
        add_in_realm(person);
    });

    _.each(page_params.realm_non_active_users, function (person: Person) {
        add(person);
    });

    _.each(page_params.cross_realm_bots, function (person: Person) {
        if (!people_dict.has(person.email)) {
            add(person);
        }
        cross_realm_dict.set(person.user_id, person);
    });

    initialize_current_user(page_params.user_id);

    delete page_params.realm_users; // We are the only consumer of this.
    delete page_params.realm_non_active_users;
    delete page_params.cross_realm_bots;
};
