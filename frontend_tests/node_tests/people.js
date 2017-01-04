add_dependencies({
    util: 'js/util.js',
});

global.stub_out_jquery();

var people = require("js/people.js");

set_global('page_params', {
    people_list: [],
    email: 'hamlet@example.com',
});
set_global('activity', {
    redraw: function () {},
});
set_global('admin', {
    show_or_hide_menu_item: function () {},
});

var _ = global._;

(function test_basics() {
    var orig_person = {
        email: 'orig@example.com',
        user_id: 31,
        full_name: 'Original',
    };
    people.add(orig_person);

    var persons = people.get_all_persons();
    assert.equal(_.size(persons), 1);
    assert.equal(persons[0].full_name, 'Original');

    var realm_persons = people.get_realm_persons();
    assert.equal(_.size(realm_persons), 0);


    var full_name = 'Isaac Newton';
    var email = 'isaac@example.com';
    var isaac = {
        email: email,
        user_id: 32,
        full_name: full_name,
    };
    people.add(isaac);

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

    people.update({email: email, is_admin: true});
    person = people.get_by_email(email);
    assert.equal(person.full_name, full_name);
    assert.equal(person.is_admin, true);

    people.update({email: email, full_name: 'Sir Isaac'});
    person = people.get_by_email(email);
    assert.equal(person.full_name, 'Sir Isaac');
    assert.equal(person.is_admin, true);

    global.page_params.email = email;

    people.update({email: email, is_admin: false});
    assert(!global.page_params.is_admin);

    people.update({email: email, full_name: 'The Godfather of Calculus'});
    assert.equal(global.page_params.fullname, 'The Godfather of Calculus');

    // Now deactivate isaac
    people.deactivate(isaac);
    person = people.realm_get(email);
    assert(!person);

    // We can still get their info for non-realm needs.
    person = people.get_by_email(email);
    assert.equal(person.email, email);

    // The original person should still be there
    person = people.get_by_email('orig@example.com');
    assert.equal(person.full_name, 'Original');
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

    // The semantics for update() are going to eventually
    // change to use user_id as a key, but now we use email
    // as a key and change attributes.  With the current
    // behavior, we don't have to make update() do anything
    // new.
    person = {
        email: 'mary@example.com',
        user_id: 42,
        full_name: 'Mary New',
    };
    people.update(person);
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
    var myself = {
        email: 'myself@example.com',
        user_id: 201,
        full_name: 'Yours Truly',
    };
    global.page_params.email = myself.email;
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
    people.add_in_realm(myself);
    people.add_in_realm(alice1);
    people.add_in_realm(bob);
    people.add_in_realm(alice2);
    var others = people.get_rest_of_realm();
    var expected = [
        { email: 'alice1@example.com', full_name: 'Alice' },
        { email: 'alice2@example.com', full_name: 'Alice' },
        { email: 'bob@example.com', full_name: 'Bob van Roberts' },
    ];
    assert.deepEqual(others, expected);

}());

people.init();

(function test_recipient_counts() {
    var email = 'anybody@example.com';
    assert.equal(people.get_recipient_count({email: email}), 0);
    people.incr_recipient_count(email);
    people.incr_recipient_count(email);
    assert.equal(people.get_recipient_count({email: email}), 2);

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
    assert.equal(filtered_people["ashton@example.com"], true);
    assert.equal(filtered_people["athens@example.com"], true);
    assert.equal(_.keys(filtered_people).length, 2);
    assert(!_.has(filtered_people, 'charles@example.com'));

    filtered_people = people.filter_people_by_search_terms(users, []);
    assert(_.isEmpty(filtered_people));

    filtered_people = people.filter_people_by_search_terms(users, ['ltorv']);
    assert.equal(_.keys(filtered_people).length, 1);
    assert(_.has(filtered_people, 'ltorvalds@example.com'));

    filtered_people = people.filter_people_by_search_terms(users, ['ch di', 'maria']);
    assert.equal(_.keys(filtered_people).length, 2);
    assert(_.has(filtered_people, 'charles@example.com'));
    assert(_.has(filtered_people, 'athens@example.com'));

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

    emails_string = 'emp402@example.com,EMP401@EXAMPLE.COM';
    var user_ids_string = people.emails_strings_to_user_ids_string(emails_string);
    assert.equal(user_ids_string, '401,402');
}());
