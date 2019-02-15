zrequire('util');
zrequire('people');

set_global('blueslip', global.make_zblueslip({
    error: false, // We check for errors in people_errors.js
}));
set_global('page_params', {});
set_global('md5', function (s) {
    return 'md5-' + s;
});
set_global('i18n', global.stub_i18n);

var me = {
    email: 'me@example.com',
    user_id: 30,
    full_name: 'Me Myself',
    timezone: 'US/Pacific',
    is_admin: false,
    is_guest: false,
    is_bot: false,
};

var isaac = {
    email: 'isaac@example.com',
    user_id: 32,
    full_name: 'Isaac Newton',
};

function initialize() {
    people.init();
    people.add(me);
    people.initialize_current_user(me.user_id);
}

initialize();

run_test('basics', () => {
    var persons = people.get_all_persons();

    assert.equal(_.size(persons), 1);
    assert.equal(persons[0].full_name, 'Me Myself');

    var realm_persons = people.get_realm_persons();
    assert.equal(_.size(realm_persons), 0);
    assert.equal(people.get_realm_count(), 0);

    var full_name = 'Isaac Newton';
    var email = 'isaac@example.com';

    assert(!people.is_known_user_id(32));
    people.add(isaac);

    assert(people.is_known_user_id(32));
    assert.equal(people.get_realm_count(), 0);

    var person = people.get_by_name(full_name);
    assert.equal(people.get_user_id(email), 32);
    assert.equal(person.email, email);
    person = people.get_by_email(email);
    assert.equal(person.full_name, full_name);
    person = people.get_active_user_for_email(email);
    assert(!person);
    people.add_in_realm(isaac);
    assert.equal(people.get_realm_count(), 1);
    person = people.get_active_user_for_email(email);
    assert.equal(person.email, email);

    realm_persons = people.get_realm_persons();
    assert.equal(_.size(realm_persons), 1);
    assert.equal(realm_persons[0].full_name, 'Isaac Newton');

    var active_user_ids = people.get_active_user_ids();
    assert.deepEqual(active_user_ids, [isaac.user_id]);
    assert.equal(people.is_active_user_for_popover(isaac.user_id), true);
    assert(people.is_valid_email_for_compose(isaac.email));

    // Now deactivate isaac
    people.deactivate(isaac);
    person = people.get_active_user_for_email(email);
    assert(!person);
    assert.equal(people.get_realm_count(), 0);
    assert.equal(people.is_active_user_for_popover(isaac.user_id), false);
    assert.equal(people.is_valid_email_for_compose(isaac.email), false);

    var bot_botson = {
        email: 'botson-bot@example.com',
        user_id: 35,
        full_name: 'Bot Botson',
        is_bot: true,
    };
    people.add_in_realm(bot_botson);
    assert.equal(people.is_active_user_for_popover(bot_botson.user_id), true);

    // Invalid user ID returns false and warns.
    blueslip.set_test_data('warn', 'Unexpectedly invalid user_id in user popover query: 123412');
    assert.equal(people.is_active_user_for_popover(123412), false);
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    blueslip.clear_test_data();

    // We can still get their info for non-realm needs.
    person = people.get_by_email(email);
    assert.equal(person.email, email);

    // The current user should still be there
    person = people.get_by_email('me@example.com');
    assert.equal(person.full_name, 'Me Myself');

    // Test undefined people
    assert.equal(people.is_cross_realm_email('unknown@example.com'), undefined);
    assert.equal(people.get_active_user_for_email('unknown@example.com'), undefined);

    // Test is_my_user_id function
    assert.equal(people.is_my_user_id(me.user_id), true);
    assert.equal(people.is_my_user_id(isaac.user_id), false);
    assert.equal(people.is_my_user_id(undefined), false);

    // Reactivating issac
    people.add_in_realm(isaac);
    var active_human_persons = people.get_active_human_persons();
    assert.equal(active_human_persons.length, 1);
    assert.deepEqual(active_human_persons, [isaac]);
});

run_test('pm_lookup_key', () => {
    assert.equal(people.pm_lookup_key('30'), '30');
    assert.equal(people.pm_lookup_key('32,30'), '32');
    assert.equal(people.pm_lookup_key('101,32,30'), '32,101');
});

run_test('get_recipients', () => {
    assert.equal(people.get_recipients('30'), 'Me Myself');
    assert.equal(people.get_recipients('30,32'), 'Isaac Newton');
});

run_test('safe_full_names', () => {
    var names = people.safe_full_names([me.user_id, isaac.user_id]);
    assert.equal(names, 'Me Myself, Isaac Newton');
});

run_test('my_custom_profile_data', () => {
    var person = people.get_by_email(me.email);
    person.profile_data = {3: 'My address', 4: 'My phone number'};
    assert.equal(people.my_custom_profile_data(3), 'My address');
    assert.equal(people.my_custom_profile_data(4), 'My phone number');
    assert.equal(people.my_custom_profile_data(undefined), undefined);
});

run_test('user_timezone', () => {
    var expected_pref = {
        timezone: 'US/Pacific',
        format: 'H:mm',
    };

    global.page_params.twenty_four_hour_time = true;
    assert.deepEqual(people.get_user_time_preferences(me.user_id), expected_pref);

    expected_pref.format = 'h:mm A';
    global.page_params.twenty_four_hour_time = false;
    assert.deepEqual(people.get_user_time_preferences(me.user_id), expected_pref);

    zrequire('actual_moment', 'moment-timezone');
    set_global('moment', function () { return global.actual_moment('20130208T080910'); });

    global.page_params.twenty_four_hour_time = true;
    assert.equal(people.get_user_time(me.user_id), '0:09');

    expected_pref.format = 'h:mm A';
    global.page_params.twenty_four_hour_time = false;
    assert.equal(people.get_user_time(me.user_id), '12:09 AM');
});

run_test('user_type', () => {
    var realm_admin = {
        email: 'realm_admin@example.com',
        user_id: 32,
        is_admin: true,
        is_guest: false,
        is_bot: false,
    };
    var guest = {
        email: 'guest@example.com',
        user_id: 33,
        is_admin: false,
        is_guest: true,
        is_bot: false,
    };
    var bot = {
        email: 'bot@example.com',
        user_id: 34,
        is_admin: false,
        is_guest: false,
        is_bot: true,
    };

    people.add(realm_admin);
    people.add(guest);
    people.add(bot);
    assert.equal(people.get_user_type(me.user_id), i18n.t('Member'));
    assert.equal(people.get_user_type(realm_admin.user_id), i18n.t('Administrator'));
    assert.equal(people.get_user_type(guest.user_id), i18n.t('Guest'));
    assert.equal(people.get_user_type(bot.user_id), i18n.t('Bot'));
});

run_test('updates', () => {
    var person = people.get_by_email('me@example.com');
    people.set_full_name(person, 'Me the Third');
    assert.equal(people.my_full_name(), 'Me the Third');
    assert.equal(person.full_name, 'Me the Third');
    assert.equal(people.get_by_name('Me the Third').email, 'me@example.com');
});

run_test('get_person_from_user_id', () => {
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
    person = people.get_active_user_for_email('mary@example.com');
    assert.equal(person, undefined);
    person = people.get_person_from_user_id(42);
    assert.equal(person.user_id, 42);
});

initialize();

run_test('set_custom_profile_field_data', () => {
    var person = people.get_by_email(me.email);
    me.profile_data = {};
    var field = {id: 3, name: 'Custom long field', type: 'text', value: 'Field value', rendered_value: '<p>Field value</p>'};
    people.set_custom_profile_field_data(person.user_id, {});
    assert.deepEqual(person.profile_data, {});
    people.set_custom_profile_field_data(person.user_id, field);
    assert.equal(person.profile_data[field.id].value, 'Field value');
    assert.equal(person.profile_data[field.id].rendered_value, '<p>Field value</p>');
});

run_test('get_rest_of_realm', () => {
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

});

initialize();

run_test('recipient_counts', () => {
    var user_id = 99;
    assert.equal(people.get_recipient_count({id: user_id}), 0);
    people.incr_recipient_count(user_id);
    people.incr_recipient_count(user_id);
    assert.equal(people.get_recipient_count({user_id: user_id}), 2);

    assert.equal(people.get_recipient_count({pm_recipient_count: 5}), 5);
});

run_test('filtered_users', () => {
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
});

people.init();

run_test('multi_user_methods', () => {
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
});

initialize();

run_test('message_methods', () => {
    var charles = {
        email: 'charles@example.com',
        user_id: 451,
        full_name: 'Charles Dickens',
        avatar_url: 'charles.com/foo.png',
        is_guest: false,
    };
    // Maria is an intentionally incomplete user object without all attributes
    var maria = {
        email: 'Athens@example.com',
        user_id: 452,
        full_name: 'Maria Athens',
    };
    people.add(charles);
    people.add(maria);

    assert.equal(people.small_avatar_url_for_person(maria),
                 'https://secure.gravatar.com/avatar/md5-athens@example.com?d=identicon&s=50');
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
    assert.equal(people.pm_perma_link(message), '#narrow/pm-with/30,451,452-group');
    assert.equal(people.pm_reply_to(message),
                 'Athens@example.com,charles@example.com');
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
    assert.equal(people.pm_perma_link(message), '#narrow/pm-with/30,452-pm');
    assert.equal(people.pm_reply_to(message),
                 'Athens@example.com');
    assert.equal(people.small_avatar_url(message),
                 'legacy.png&s=50');

    message = {
        avatar_url: undefined,
        sender_id: maria.user_id,
    };
    assert.equal(people.small_avatar_url(message),
                 'https://secure.gravatar.com/avatar/md5-athens@example.com?d=identicon&s=50'
    );

    message = {
        avatar_url: undefined,
        sender_email: 'foo@example.com',
        sender_id: 9999999,
    };
    assert.equal(people.small_avatar_url(message),
                 'https://secure.gravatar.com/avatar/md5-foo@example.com?d=identicon&s=50'
    );

    message = {
        type: 'private',
        display_recipient: [
            {user_id: me.user_id},
        ],
    };
    assert.equal(people.pm_with_url(message), '#narrow/pm-with/30-me');
    assert.equal(people.pm_perma_link(message), '#narrow/pm-with/30-pm');

    message = { type: 'stream' };
    assert.equal(people.pm_with_user_ids(message), undefined);
    assert.equal(people.all_user_ids_in_pm(message), undefined);

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

    // Test sender_is_guest
    var polonius = {
        email: 'polonius@example.com',
        user_id: 43,
        full_name: 'Guest User',
        is_bot: false,
        is_guest: true,
    };
    people.add(polonius);

    message = { sender_id: polonius.user_id };
    assert.equal(people.sender_is_guest(message), true);

    message = { sender_id: maria.user_id };
    assert.equal(people.sender_is_guest(message), undefined);

    message = { sender_id: charles.user_id };
    assert.equal(people.sender_is_guest(message), false);

    message = { sender_id: undefined };
    assert.equal(people.sender_is_guest(message), false);
});

initialize();

run_test('extract_people_from_message', () => {
    var unknown_user = {
        email: 'unknown@example.com',
        user_id: 500,
        unknown_local_echo_user: true,
    };

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
    assert(!people.is_known_user_id(maria.user_id));

    var reported;
    people.report_late_add = function (user_id, email) {
        assert.equal(user_id, maria.user_id);
        assert.equal(email, maria.email);
        reported = true;
    };

    people.extract_people_from_message(message);
    assert(people.is_known_user_id(maria.user_id));
    assert(reported);

    // Get line coverage
    people.report_late_add = function () {
        throw Error('unexpected late add');
    };

    message = {
        type: 'private',
        display_recipient: [unknown_user],
    };
    people.extract_people_from_message(message);
});

initialize();

run_test('maybe_incr_recipient_count', () => {
    var maria = {
        email: 'athens@example.com',
        user_id: 452,
        full_name: 'Maria Athens',
    };
    people.add_in_realm(maria);

    var unknown_user = {
        email: 'unknown@example.com',
        user_id: 500,
        unknown_local_echo_user: true,
    };

    var message = {
        type: 'private',
        display_recipient: [maria],
        sent_by_me: true,
    };
    assert.equal(people.get_recipient_count(maria), 0);
    people.maybe_incr_recipient_count(message);
    assert.equal(people.get_recipient_count(maria), 1);

    // Test all the no-op conditions to get test
    // coverage.
    message = {
        type: 'private',
        sent_by_me: false,
        display_recipient: [maria],
    };
    people.maybe_incr_recipient_count(message);
    assert.equal(people.get_recipient_count(maria), 1);

    message = {
        type: 'private',
        sent_by_me: true,
        display_recipient: [unknown_user],
    };
    people.maybe_incr_recipient_count(message);
    assert.equal(people.get_recipient_count(maria), 1);

    message = {
        type: 'stream',
    };
    people.maybe_incr_recipient_count(message);
    assert.equal(people.get_recipient_count(maria), 1);
});

run_test('slugs', () => {
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
    assert.equal(people.emails_to_slug('does@not.exist'), undefined);
});

initialize();

run_test('updates', () => {
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
    assert.equal(people.get_active_user_for_email(old_email).user_id, user_id);
    assert (!people.is_cross_realm_email(old_email));

    assert.equal(people.get_by_email(new_email), undefined);

    // DO THE EMAIL UPDATE HERE.
    people.update_email(user_id, new_email);

    // Now look up using the new email.
    assert.equal(people.get_by_email(new_email).user_id, user_id);
    assert.equal(people.get_active_user_for_email(new_email).user_id, user_id);
    assert (!people.is_cross_realm_email(new_email));

    var all_people = people.get_all_persons();
    assert.equal(all_people.length, 2);

    person = _.filter(all_people, function (p) {
        return p.email === new_email;
    })[0];
    assert.equal(person.full_name, 'Foo Barson');

    // Test shim where we can still retrieve user info using the
    // old email.
    blueslip.set_test_data('warn',
                           'Obsolete email passed to get_by_email: ' +
                           'FOO@example.com new email = bar@example.com');
    person = people.get_by_email(old_email);
    assert.equal(person.user_id, user_id);
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    blueslip.clear_test_data();
});

initialize();

run_test('update_email_in_reply_to', () => {
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
});

initialize();

run_test('track_duplicate_full_names', () => {
    var stephen1 = {
        email: 'stephen-the-author@example.com',
        user_id: 601,
        full_name: 'Stephen King',
    };
    var stephen2 = {
        email: 'stephen-the-explorer@example.com',
        user_id: 602,
        full_name: 'Stephen King',
    };
    var maria = {
        email: 'athens@example.com',
        user_id: 603,
        full_name: 'Maria Athens',
    };
    people.add(stephen1);
    people.add(stephen2);
    people.add(maria);
    assert(people.is_duplicate_full_name('Stephen King'));
    assert(!people.is_duplicate_full_name('Maria Athens'));
    assert(!people.is_duplicate_full_name('Some Random Name'));
    people.set_full_name(stephen2, 'Stephen King JP');
    assert(!people.is_duplicate_full_name('Stephen King'));
    assert(!people.is_duplicate_full_name('Stephen King JP'));
});

run_test('track_duplicate_full_names', () => {
    var stephen1 = {
        email: 'stephen-the-author@example.com',
        user_id: 601,
        full_name: 'Stephen King',
    };
    var stephen2 = {
        email: 'stephen-the-explorer@example.com',
        user_id: 602,
        full_name: 'Stephen King',
    };
    var maria = {
        email: 'athens@example.com',
        user_id: 603,
        full_name: 'Maria Athens',
    };
    people.add(stephen1);
    people.add(stephen2);
    people.add(maria);

    blueslip.set_test_data('warn', 'get_mention_syntax called without user_id.');
    assert.equal(people.get_mention_syntax('Stephen King'), '@**Stephen King**');
    assert.equal(blueslip.get_test_logs('warn').length, 1);
    blueslip.clear_test_data();
    assert.equal(people.get_mention_syntax('Stephen King', 601), '@**Stephen King|601**');
    assert.equal(people.get_mention_syntax('Stephen King', 602), '@**Stephen King|602**');
    assert.equal(people.get_mention_syntax('Maria Athens', 603), '@**Maria Athens**');
});

run_test('initialize', () => {
    people.init();

    global.page_params.realm_non_active_users = [
        {
            email: 'retiree@example.com',
            user_id: 15,
            full_name: 'Retiree',
        },
    ];

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

    assert.equal(people.get_active_user_for_email('alice@example.com').full_name, 'Alice');
    assert.equal(people.is_active_user_for_popover(17), true);
    assert(people.is_cross_realm_email('bot@example.com'));
    assert(people.is_valid_email_for_compose('bot@example.com'));
    assert(people.is_valid_email_for_compose('alice@example.com'));
    assert(!people.is_valid_email_for_compose('retiree@example.com'));
    assert(!people.is_valid_email_for_compose('totally-bogus-username@example.com'));
    assert(people.is_valid_bulk_emails_for_compose(['bot@example.com', 'alice@example.com']));
    assert(!people.is_valid_bulk_emails_for_compose(['not@valid.com', 'alice@example.com']));
    assert(people.is_my_user_id(42));

    var fetched_retiree = people.get_person_from_user_id(15);
    assert.equal(fetched_retiree.full_name, 'Retiree');

    assert.equal(global.page_params.realm_users, undefined);
    assert.equal(global.page_params.cross_realm_bots, undefined);
    assert.equal(global.page_params.realm_non_active_users, undefined);
});
