zrequire('people');
zrequire('user_pill');

set_global('page_params', {
});

var alice = {
    email: 'alice@example.com',
    user_id: 99,
    full_name: 'Alice Barson',
};

var isaac = {
    email: 'isaac@example.com',
    user_id: 102,
    full_name: 'Isaac Newton',
};

var bogus_item = {
    email: 'bogus@example.com',
    display_value: 'bogus@example.com',
};

var isaac_item = {
    email: 'isaac@example.com',
    display_value: 'Isaac Newton',
    user_id: isaac.user_id,
};

(function setup() {
    people.add_in_realm(alice);
    people.add_in_realm(isaac);
}());

(function test_create_item() {

    function test_create_item(email, current_items, expected_item) {
        var item = user_pill.create_item_from_email(email, current_items);
        assert.deepEqual(item, expected_item);
    }

    page_params.realm_is_zephyr_mirror_realm = true;

    test_create_item('bogus@example.com', [], bogus_item);
    test_create_item('bogus@example.com', [bogus_item], undefined);

    test_create_item('isaac@example.com', [], isaac_item);
    test_create_item('isaac@example.com', [isaac_item], undefined);

    page_params.realm_is_zephyr_mirror_realm = false;

    test_create_item('bogus@example.com', [], undefined);
    test_create_item('isaac@example.com', [], isaac_item);
    test_create_item('isaac@example.com', [isaac_item], undefined);
}());

(function test_get_email() {
    assert.equal(user_pill.get_email_from_item({email: 'foo@example.com'}), 'foo@example.com');
}());

(function test_append() {
    var appended;
    var cleared;

    function fake_append(opts) {
        appended = true;
        assert.equal(opts.email, isaac.email);
        assert.equal(opts.display_value, isaac.full_name);
        assert.equal(opts.user_id, isaac.user_id);
    }

    function fake_clear() {
        cleared = true;
    }

    var pill_widget = {
        appendValidatedData: fake_append,
        clear_text: fake_clear,
    };

    user_pill.append_person({
        person: isaac,
        pill_widget: pill_widget,
    });

    assert(appended);
    assert(cleared);
}());

(function test_get_items() {
    var items = [isaac_item, bogus_item];

    var pill_widget = {
        items: function () { return items; },
    };

    assert.deepEqual(user_pill.get_user_ids(pill_widget), [isaac.user_id]);
}());

(function test_typeahead() {
    var items = [isaac_item, bogus_item];

    var pill_widget = {
        items: function () { return items; },
    };

    // Both alice and isaac are in our realm, but isaac will be
    // excluded by virtue of already being one of the widget items.
    // And then bogus_item is just a red herring to test robustness.
    var result = user_pill.typeahead_source(pill_widget);
    assert.deepEqual(result, [alice]);
}());
