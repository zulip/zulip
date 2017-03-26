add_dependencies({
    util: 'js/util.js',
});

global.stub_out_jquery();

var people = require("js/people.js");
set_global('blueslip', {});

var _ = global._;

var me = {
    email: 'me@example.com',
    user_id: 30,
    full_name: 'Me Myself',
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

    var person = people.get_by_name(full_name);
    assert.equal(people.get_user_id(email), 32);
    assert.equal(person.email, email);
    person = people.get_by_email(email);
    assert.equal(person.full_name, full_name);
    person = people.realm_get(email);
    assert(!person);
    people.add_in_realm(isaac);
    person = people.realm_get(email);
    assert.equal(person.email, email);

    realm_persons = people.get_realm_persons();
    assert.equal(_.size(realm_persons), 1);
    assert.equal(realm_persons[0].full_name, 'Isaac Newton');

    // Now deactivate isaac
    people.deactivate(isaac);
    person = people.realm_get(email);
    assert(!person);

    // We can still get their info for non-realm needs.
    person = people.get_by_email(email);
    assert.equal(person.email, email);

    // The current user should still be there
    person = people.get_by_email('me@example.com');
    assert.equal(person.full_name, 'Me Myself');
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

    people.add_in_realm(charles);
    people.add_in_realm(maria);
    people.add_in_realm(ashton);
    people.add_in_realm(linus);

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

    var slug = people.emails_to_slug(emails_string);
    assert.equal(slug, '401,402-group');
}());

initialize();

(function test_pm_with_url() {
    var charles = {
        email: 'charles@example.com',
        user_id: 451,
        full_name: 'Charles Dickens',
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
    };
    assert.equal(people.pm_with_url(message), '#narrow/pm-with/451,452-group');

    message = {
        type: 'private',
        display_recipient: [
            {id: maria.user_id},
            {user_id: me.user_id},
        ],
    };
    assert.equal(people.pm_with_url(message), '#narrow/pm-with/452-athens');

    message = {
        type: 'private',
        display_recipient: [
            {user_id: me.user_id},
        ],
    };
    assert.equal(people.pm_with_url(message), '#narrow/pm-with/30-me');
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
}());

