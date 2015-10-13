add_dependencies({
    util: 'js/util.js'
});

var people = require("js/people.js");

set_global('page_params', {
    people_list: []
});
set_global('activity', {
    set_user_statuses: function () {}
});
set_global('admin', {
    show_or_hide_menu_item: function () {}
});

(function test_basics() {
    var orig_person = {
        email: 'orig@example.com',
        full_name: 'Original'
    };
    people.add(orig_person);

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
}());
