var people = require("js/people.js");

set_global('page_params', {
    people_list: []
});
set_global('activity', {
    set_user_statuses: function () {}
});

(function test_basics() {
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

    people.remove(person);
    person = people.get_by_email(email);
    assert(!person);
}());
