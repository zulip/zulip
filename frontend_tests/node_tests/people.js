add_dependencies({
    util: 'js/util.js'
});

global.stub_out_jquery();

var people = require("js/people.js");

set_global('page_params', {
    people_list: [],
    email: 'hamlet@example.com'
});
set_global('activity', {
    set_user_statuses: function () {}
});
set_global('admin', {
    show_or_hide_menu_item: function () {}
});

var _ = global._;

(function test_basics() {
    var orig_person = {
        email: 'orig@example.com',
        full_name: 'Original'
    };
    people.add(orig_person);

    var persons = people.get_all_persons();
    assert.equal(_.size(persons), 1);
    assert.equal(persons[0].full_name, 'Original');

    var full_name = 'Isaac Newton';
    var email = 'isaac@example.com';
    var isaac = {
        email: email,
        full_name: full_name
    };
    people.add(isaac);

    var person = people.get_by_name(full_name);
    assert.equal(person.email, email);
    person = people.get_by_email(email);
    assert.equal(person.full_name, full_name);
    person = people.realm_get(email);
    assert(!person);
    people.add_in_realm(isaac);
    person = people.realm_get(email);
    assert.equal(person.email, email);

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

    // Now remove isaac
    people.remove(isaac);
    person = people.get_by_email(email);
    assert(!person);

    // The original person should still be there
    person = people.get_by_email('orig@example.com');
    assert.equal(person.full_name, 'Original');
}());

(function test_reify() {
    var full_person = {
        email: 'foo@example.com',
        full_name: 'Foo Barson'
    };

    // If we don't have a skeleton object, this should quietly succeed.
    people.reify(full_person);

    var skeleton = {
        email: 'foo@example.com',
        full_name: 'foo@example.com',
        skeleton: true
    };
    people.add(skeleton);

    people.reify(full_person);
    var person = people.get_by_email('foo@example.com');
    assert.equal(person.full_name, 'Foo Barson');

    // Our follow-up reify() call should also quietly succeed.
    people.reify(full_person);
}());

(function test_get_rest_of_realm() {
    var myself = {
        email: 'myself@example.com',
        full_name: 'Yours Truly'
    };
    global.page_params.email = myself.email;
    var alice1 = {
        email: 'alice1@example.com',
        full_name: 'Alice'
    };
    var alice2 = {
        email: 'alice2@example.com',
        full_name: 'Alice'
    };
    var bob = {
        email: 'bob@example.com',
        full_name: 'Bob van Roberts'
    };
    people.add_in_realm(myself);
    people.add_in_realm(alice1);
    people.add_in_realm(bob);
    people.add_in_realm(alice2);
    var others = people.get_rest_of_realm();
    var expected = [
        { email: 'alice1@example.com', full_name: 'Alice' },
        { email: 'alice2@example.com', full_name: 'Alice' },
        { email: 'bob@example.com', full_name: 'Bob van Roberts' }
    ];
    assert.deepEqual(others, expected);

    people.remove(alice1);
    people.remove(alice2);
    people.remove(bob);
}());

(function test_filtered_users() {
     var charles = {
        email: 'charles@example.com',
        full_name: 'Charles Dickens'
    };
    var maria = {
        email: 'athens@example.com',
        full_name: 'Maria Athens'
    };
    var ashton = {
        email: 'ashton@example.com',
        full_name: 'Ashton Smith'
    };

    people.add_in_realm(charles);
    people.add_in_realm(maria);
    people.add_in_realm(ashton);
    var search_term = 'a';
    var users = people.get_rest_of_realm();
    var filtered_people = people.filter_people_by_search_terms(users, search_term);
    var expected = [
        { email: 'athens@example.com', full_name: 'Maria Athens' },
        { email: 'ashton@example.com', full_name: 'Ashton Smith' }
    ];
    assert.equal(filtered_people["ashton@example.com"], true);
    assert.equal(filtered_people["athens@example.com"], true);
    assert.equal(_.keys(filtered_people).length, 2);
    assert(!_.has(filtered_people, 'charles@example.com'));

    search_term = '';
    filtered_people = people.filter_people_by_search_terms(users, search_term);
    assert(_.isEmpty(filtered_people));

    people.remove(charles);
    people.remove(maria);
    people.remove(ashton);
}());
