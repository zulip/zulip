add_dependencies({
    util: 'js/util.js',
});

var people = require("js/people.js");
set_global('blueslip', {});
set_global('page_params', {});

var _ = global._;

var me = {
    email: 'me@example.com',
    user_id: 30,
    full_name: 'Me Myself',
    timezone: 'US/Pacific',
};

function initialize() {
    people.init();
    people.add(me);
    people.initialize_current_user(me.user_id);
}

initialize();

(function test_basics() {
    var persons = people.get_all_persons();

    assert.equal(_.size(persons), 1);
    assert.equal(persons[0].full_name, 'Me Myself');

    var realm_persons = people.get_realm_persons();
    assert.equal(_.size(realm_persons), 0);
    assert.equal(people.get_realm_count(), 0);

    var full_name = 'Isaac Newton';
    var email = 'isaac@example.com';
    var isaac = {
        email: email,
        user_id: 32,
        full_name: full_name,
    };

    assert(!people.is_known_user_id(32));
    people.add(isaac);
    assert(people.is_known_user_id(32));
    assert.equal(people.get_realm_count(), 0);

    var person = people.get_by_name(full_name);
    assert.equal(people.get_user_id(email), 32);
    assert.equal(person.email, email);
    person = people.get_by_email(email);
    assert.equal(person.full_name, full_name);
    person = people.realm_get(email);
    assert(!person);
    people.add_in_realm(isaac);
    assert.equal(people.get_realm_count(), 1);
    person = people.realm_get(email);
    assert.equal(person.email, email);

    realm_persons = people.get_realm_persons();
    assert.equal(_.size(realm_persons), 1);
    assert.equal(realm_persons[0].full_name, 'Isaac Newton');

    // Now deactivate isaac
    people.deactivate(isaac);
    person = people.realm_get(email);
    assert(!person);
    assert.equal(people.get_realm_count(), 0);

    // We can still get their info for non-realm needs.
    person = people.get_by_email(email);
    assert.equal(person.email, email);

    // The current user should still be there
    person = people.get_by_email('me@example.com');
    assert.equal(person.full_name, 'Me Myself');

    // Test undefined people
    assert.equal(people.is_cross_realm_email('unknown@example.com'), undefined);
    assert.equal(people.realm_get('unknown@example.com'), undefined);

    // Test is_my_user_id function
    assert.equal(people.is_my_user_id(me.user_id), true);
    assert.equal(people.is_my_user_id(isaac.user_id), false);
    assert.equal(people.is_my_user_id(undefined), false);
}());

(function test_pm_lookup_key() {
    assert.equal(people.pm_lookup_key('30'), '30');
    assert.equal(people.pm_lookup_key('32,30'), '32');
    assert.equal(people.pm_lookup_key('101,32,30'), '32,101');
}());

(function test_get_recipients() {
    assert.equal(people.get_recipients('30'), 'Me Myself');
    assert.equal(people.get_recipients('30,32'), 'Isaac Newton');
}());

(function test_user_timezone() {
    var expected_pref = {
        timezone: 'US/Pacific',
        format: 'HH:mm',
    };

    global.page_params.twenty_four_hour_time = true;
    assert.deepEqual(people.get_user_time_preferences(me.user_id), expected_pref);

    expected_pref.format = 'hh:mm A';
    global.page_params.twenty_four_hour_time = false;
    assert.deepEqual(people.get_user_time_preferences(me.user_id), expected_pref);

    var actual_moment = require('moment-timezone');
    set_global('moment', function () { return actual_moment('20130208T080910'); });

    global.page_params.twenty_four_hour_time = true;
    assert.equal(people.get_user_time(me.user_id), '00:09');

    expected_pref.format = 'hh:mm A';
    global.page_params.twenty_four_hour_time = false;
    assert.equal(people.get_user_time(me.user_id), '12:09 AM');
}());

(function test_updates() {
    var person = people.get_by_email('me@example.com');
    people.set_full_name(person, 'Me the Third');
    assert.equal(people.my_full_name(), 'Me the Third');
    assert.equal(person.full_name, 'Me the Third');
    assert.equal(people.get_by_name('Me the Third').email, 'me@example.com');
}());

(function test_get_person_from_user_id() {
    var person = {
        email: 'mary@example.com',
        user_id: 42,
        full_name: 'Mary',
    };
    people.add(person);
    person = people.get_by_email('mary@example.com');
    assert.equal(person.full_name, 'Mary');
    person = people.get_person_from_user_id(42);
    assert.equal(person.email, 'mary@example.com');

    people.set_full_name(person, 'Mary New');
    person = people.get_person_from_user_id(42);
    assert.equal(person.full_name, 'Mary New');

    // deactivate() should eventually just take a user_id, but
    // now it takes a full person object.  Note that deactivate()
    // won't actually make the user disappear completely.
    people.deactivate(person);
    person = people.realm_get('mary@example.com');
    assert.equal(person, undefined);
    person = people.get_person_from_user_id(42);
    assert.equal(person.user_id, 42);
}());

(function test_get_rest_of_realm() {
    var alice1 = {
        email: 'alice1@example.com',
        user_id: 202,
        full_name: 'Alice',
    };
    var alice2 = {
        email: 'alice2@example.com',
        user_id: 203,
        full_name: 'Alice',
    };
    var bob = {
        email: 'bob@example.com',
        user_id: 204,
        full_name: 'Bob van Roberts',
    };
    people.add_in_realm(alice1);
    people.add_in_realm(bob);
    people.add_in_realm(alice2);
    assert.equal(people.get_realm_count(), 3);

    var others = people.get_rest_of_realm();
    var expected = [
        { email: 'alice1@example.com', user_id: 202, full_name: 'Alice' },
        { email: 'alice2@example.com', user_id: 203, full_name: 'Alice' },
        { email: 'bob@example.com', user_id: 204, full_name: 'Bob van Roberts' },
    ];
    assert.deepEqual(others, expected);

}());

initialize();

(function test_recipient_counts() {
    var user_id = 99;
    assert.equal(people.get_recipient_count({id: user_id}), 0);
    people.incr_recipient_count(user_id);
    people.incr_recipient_count(user_id);
    assert.equal(people.get_recipient_count({user_id: user_id}), 2);

    assert.equal(people.get_recipient_count({pm_recipient_count: 5}), 5);
}());

(function test_filtered_users() {
     var charles = {
        email: 'charles@example.com',
        user_id: 301,
        full_name: 'Charles Dickens',
    };
    var maria = {
        email: 'athens@example.com',
        user_id: 302,
        full_name: 'Maria Athens',
    };
    var ashton = {
        email: 'ashton@example.com',
        user_id: 303,
        full_name: 'Ashton Smith',
    };
    var linus = {
        email: 'ltorvalds@example.com',
        user_id: 304,
        full_name: 'Linus Torvalds',
    };
    var noah = {
        email: 'emnoa@example.com',
        user_id: 305,
        full_name: 'Nöôáàh Ëmerson',
    };
    var plain_noah = {
        email: 'otheremnoa@example.com',
        user_id: 306,
        full_name: 'Nooaah Emerson',
    };

    people.add_in_realm(charles);
    people.add_in_realm(maria);
    people.add_in_realm(ashton);
    people.add_in_realm(linus);
    people.add_in_realm(noah);
    people.add_in_realm(plain_noah);

    var search_term = 'a';
    var users = people.get_rest_of_realm();
    var filtered_people = people.filter_people_by_search_terms(users, [search_term]);
    assert.equal(filtered_people.num_items(), 2);
    assert(filtered_people.has(ashton.user_id));
    assert(filtered_people.has(maria.user_id));
    assert(!filtered_people.has(charles.user_id));

    filtered_people = people.filter_people_by_search_terms(users, []);
    assert.equal(filtered_people.num_items(), 0);

    filtered_people = people.filter_people_by_search_terms(users, ['ltorv']);
    assert.equal(filtered_people.num_items(), 1);
    assert(filtered_people.has(linus.user_id));

    filtered_people = people.filter_people_by_search_terms(users, ['ch di', 'maria']);
    assert.equal(filtered_people.num_items(), 2);
    assert(filtered_people.has(charles.user_id));
    assert(filtered_people.has(maria.user_id));

    // Test filtering of names with diacritics
    // This should match Nöôáàh by ignoring diacritics, and also match Nooaah
    filtered_people = people.filter_people_by_search_terms(users, ['noOa']);
    assert.equal(filtered_people.num_items(), 2);
    assert(filtered_people.has(noah.user_id));
    assert(filtered_people.has(plain_noah.user_id));

    // This should match ëmerson, but not emerson
    filtered_people = people.filter_people_by_search_terms(users, ['ëm']);
    assert.equal(filtered_people.num_items(), 1);
    assert(filtered_people.has(noah.user_id));

    // Test filtering with undefined user
    var foo = {
        email: 'foo@example.com',
        user_id: 42,
        full_name: 'Foo Bar',
    };
    users.push(foo);

    filtered_people = people.filter_people_by_search_terms(users, ['ltorv']);
    assert.equal(filtered_people.num_items(), 1);
    assert(filtered_people.has(linus.user_id));
}());

people.init();

(function test_multi_user_methods() {
    var emp401 = {
        email: 'emp401@example.com',
        user_id: 401,
        full_name: 'whatever 401',
    };
    var emp402 = {
        email: 'EMP402@example.com',
        user_id: 402,
        full_name: 'whatever 402',
    };

    people.add_in_realm(emp401);
    people.add_in_realm(emp402);

    var emails_string = people.user_ids_string_to_emails_string('402,401');
    assert.equal(emails_string, 'emp401@example.com,emp402@example.com');

    emails_string = people.slug_to_emails('402,401-group');
    assert.equal(emails_string, 'emp401@example.com,emp402@example.com');

    emails_string = 'emp402@example.com,EMP401@EXAMPLE.COM';
    var user_ids_string = people.emails_strings_to_user_ids_string(emails_string);
    assert.equal(user_ids_string, '401,402');

    user_ids_string = people.reply_to_to_user_ids_string(emails_string);
    assert.equal(user_ids_string, '401,402');

    var slug = people.emails_to_slug(emails_string);
    assert.equal(slug, '401,402-group');

    assert.equal(people.reply_to_to_user_ids_string('invalid@example.com'), undefined);
}());

initialize();

(function test_message_methods() {
    var charles = {
        email: 'charles@example.com',
        user_id: 451,
        full_name: 'Charles Dickens',
        avatar_url: 'charles.com/foo.png',
    };
    var maria = {
        email: 'athens@example.com',
        user_id: 452,
        full_name: 'Maria Athens',
    };
    people.add(charles);
    people.add(maria);

    var message = {
        type: 'private',
        display_recipient: [
            {id: maria.user_id},
            {id: me.user_id},
            {user_id: charles.user_id},
        ],
        sender_id: charles.user_id,
    };
    assert.equal(people.pm_with_url(message), '#narrow/pm-with/451,452-group');
    assert.equal(people.pm_reply_to(message),
        'athens@example.com,charles@example.com');
    assert.equal(people.small_avatar_url(message),
        'charles.com/foo.png&s=50');

    message = {
        type: 'private',
        display_recipient: [
            {id: maria.user_id},
            {user_id: me.user_id},
        ],
        avatar_url: 'legacy.png',
    };
    assert.equal(people.pm_with_url(message), '#narrow/pm-with/452-athens');
    assert.equal(people.pm_reply_to(message),
        'athens@example.com');
    assert.equal(people.small_avatar_url(message),
        'legacy.png&s=50');

    message = {
        type: 'private',
        display_recipient: [
            {user_id: me.user_id},
        ],
    };
    assert.equal(people.pm_with_url(message), '#narrow/pm-with/30-me');

    message = { type: 'stream' };
    assert.equal(people.pm_with_user_ids(message), undefined);

    // Test undefined user_ids
    assert.equal(people.pm_reply_to(message), undefined);
    assert.equal(people.pm_reply_user_string(message), undefined);
    assert.equal(people.pm_with_url(message), undefined);

    // Test sender_is_bot
    var bot = {
        email: 'bot@example.com',
        user_id: 42,
        full_name: 'Test Bot',
        is_bot: true,
    };
    people.add(bot);

    message = { sender_id: bot.user_id };
    assert.equal(people.sender_is_bot(message), true);

    message = { sender_id: maria.user_id };
    assert.equal(people.sender_is_bot(message), undefined);

    message = { sender_id: undefined };
    assert.equal(people.sender_is_bot(message), false);
}());

initialize();

(function test_extract_people_from_message() {
    var maria = {
        email: 'athens@example.com',
        user_id: 452,
        full_name: 'Maria Athens',
    };

    var message = {
        type: 'stream',
        sender_full_name: maria.full_name,
        sender_id: maria.user_id,
        sender_email: maria.email,
    };
    people.extract_people_from_message(message);
    assert(people.is_known_user_id(maria.user_id));

    message = {
        type: 'private',
        display_recipient: [maria],
        sent_by_me: true,
    };
    people.extract_people_from_message(message);
    assert.equal(people.get_recipient_count(maria), 1);
}());

(function test_slugs() {
    var person = {
        email: 'deBBie71@example.com',
        user_id: 501,
        full_name: 'Debra Henton',
    };
    people.add(person);

    var slug = people.emails_to_slug(person.email);
    assert.equal(slug, '501-debbie71');

    var email = people.slug_to_emails(slug);
    assert.equal(email, 'debbie71@example.com');

    // Test undefined slug
    people.emails_strings_to_user_ids_string = function () { return undefined; };
    assert.equal(people.emails_to_slug(), undefined);
}());

initialize();

(function test_updates() {
    var old_email = 'FOO@example.com';
    var new_email = 'bar@example.com';
    var user_id = 502;

    var person = {
        email: old_email,
        user_id: user_id,
        full_name: 'Foo Barson',
    };
    people.add_in_realm(person);

    // Do sanity checks on our data.
    assert.equal(people.get_by_email(old_email).user_id, user_id);
    assert.equal(people.realm_get(old_email).user_id, user_id);
    assert (!people.is_cross_realm_email(old_email));

    assert.equal(people.get_by_email(new_email), undefined);

    // DO THE EMAIL UPDATE HERE.
    people.update_email(user_id, new_email);

    // Now look up using the new email.
    assert.equal(people.get_by_email(new_email).user_id, user_id);
    assert.equal(people.realm_get(new_email).user_id, user_id);
    assert (!people.is_cross_realm_email(new_email));

    var all_people = people.get_all_persons();
    assert.equal(all_people.length, 2);

    person = _.filter(all_people, function (p) {
        return (p.email === new_email);
    })[0];
    assert.equal(person.full_name, 'Foo Barson');

    // Test shim where we can still retrieve user info using the
    // old email.
    var warning;
    global.blueslip.warn = function (w) {
        warning = w;
    };

    person = people.get_by_email(old_email);
    assert(/Obsolete email.*FOO.*bar/.test(warning));
    assert.equal(person.user_id, user_id);
}());

initialize();

(function test_update_email_in_reply_to() {
    var charles = {
        email: 'charles@example.com',
        user_id: 601,
        full_name: 'Charles Dickens',
    };
    var maria = {
        email: 'athens@example.com',
        user_id: 602,
        full_name: 'Maria Athens',
    };
    people.add(charles);
    people.add(maria);

    var reply_to = '    charles@example.com,   athens@example.com';
    assert.equal(
        people.update_email_in_reply_to(reply_to, 9999, 'whatever'),
        reply_to
    );
    assert.equal(
        people.update_email_in_reply_to(reply_to, maria.user_id, 'maria@example.com'),
        'charles@example.com,maria@example.com'
    );

    reply_to = '    charles@example.com,   athens@example.com, unknown@example.com';
    assert.equal(
        people.update_email_in_reply_to(reply_to, 9999, 'whatever'),
        reply_to
    );
}());

(function test_blueslip() {
    var unknown_email = "alicebobfred@example.com";

    global.blueslip.debug = function (msg) {
        assert.equal(msg, 'User email operand unknown: ' + unknown_email);
    };
    people.id_matches_email_operand(42, unknown_email);

    global.blueslip.error = function (msg) {
        assert.equal(msg, 'Unknown email for get_user_id: ' + unknown_email);
    };
    people.get_user_id(unknown_email);

    var person = {
        email: 'person@example.com',
        user_id: undefined,
        full_name: 'Person Person',
    };
    people.add(person);

    global.blueslip.error = function (msg) {
        assert.equal(msg, 'No userid found for person@example.com');
    };
    var user_id = people.get_user_id('person@example.com');
    assert.equal(user_id, undefined);

    global.blueslip.error = function (msg) {
        assert.equal(msg, 'Unknown user ids: 1,2');
    };
    people.user_ids_string_to_emails_string('1,2');

    global.blueslip.warn = function (msg) {
        assert.equal(msg, 'Unknown emails: ' + unknown_email);
    };
    people.email_list_to_user_ids_string(unknown_email);

    var message = {
        type: 'private',
        display_recipient: [],
        sender_id: me.user_id,
    };
    global.blueslip.error = function (msg) {
        assert.equal(msg, 'Empty recipient list in message');
    };
    people.pm_with_user_ids(message);
    people.group_pm_with_user_ids(message);

    var charles = {
        email: 'charles@example.com',
        user_id: 451,
        full_name: 'Charles Dickens',
        avatar_url: 'charles.com/foo.png',
    };
    var maria = {
        email: 'athens@example.com',
        user_id: 452,
        full_name: 'Maria Athens',
    };
    people.add(charles);
    people.add(maria);

    message = {
        type: 'private',
        display_recipient: [
            {id: maria.user_id},
            {id: 42},
            {user_id: charles.user_id},
        ],
        sender_id: charles.user_id,
    };
    global.blueslip.error = function (msg) {
        assert.equal(msg, 'Unknown user id in message: 42');
    };
    var reply_to = people.pm_reply_to(message);
    assert(reply_to.indexOf('?') > -1);

    people.pm_with_user_ids = function () { return [42]; };
    people.get_person_from_user_id = function () { return undefined; };
    global.blueslip.error = function (msg) {
        assert.equal(msg, 'Unknown people in message');
    };
    var uri = people.pm_with_url({});
    assert.equal(uri.indexOf('unk'), uri.length - 3);
}());

(function test_initialize() {
    people.init();

    global.page_params.realm_users = [
        {
            email: 'alice@example.com',
            user_id: 16,
            full_name: 'Alice',
        },
    ];
    global.page_params.cross_realm_bots = [
        {
            email: 'bot@example.com',
            user_id: 17,
            full_name: 'Test Bot',
        },
    ];
    global.page_params.user_id = 42;

    people.initialize();

    assert.equal(people.realm_get('alice@example.com').full_name, 'Alice');
    assert(people.is_cross_realm_email('bot@example.com'));
    assert(people.is_my_user_id(42));

    assert.equal(global.page_params.realm_users, undefined);
    assert.equal(global.page_params.cross_realm_bots, undefined);
}());
