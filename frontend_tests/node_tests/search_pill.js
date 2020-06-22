zrequire('search_pill');
zrequire('input_pill');
zrequire('people');
zrequire('Filter', 'js/filter');
set_global('Handlebars', global.make_handlebars());

const is_starred_item = {
    display_value: 'is:starred',
    stored_value: 'is:starred',
    description: 'starred messages',
};

const is_private_item = {
    display_value: 'is:private',
    stored_value: 'is:private',
    description: 'private messages',
};

const steven = {
    email: 'steven@example.com',
    delivery_email: 'steven-delivery@example.com',
    user_id: 77,
    full_name: 'Steven',
};

run_test('create_item', () => {

    function test_create_item(search_string, current_items, expected_item) {
        const item = search_pill.create_item_from_search_string(search_string, current_items);
        assert.deepEqual(item, expected_item);
    }

    test_create_item('is:starred', [], is_starred_item);
});

run_test('get_search_string', () => {
    assert.equal(search_pill.get_search_string_from_item(is_starred_item), 'is:starred');
});

run_test('append', () => {
    let appended;
    let cleared;

    function fake_append(search_string) {
        appended = true;
        assert.equal(search_string, is_starred_item.stored_value);
    }

    function fake_clear() {
        cleared = true;
    }

    const pill_widget = {
        appendValue: fake_append,
        clear_text: fake_clear,
    };

    search_pill.append_search_string(is_starred_item.stored_value, pill_widget);

    assert(appended);
    assert(cleared);
});

run_test('get_items', () => {
    const items = [is_starred_item, is_private_item];

    const pill_widget = {
        items: function () { return items; },
    };

    assert.deepEqual(search_pill.get_search_string_for_current_filter(pill_widget),
                     is_starred_item.stored_value + ' ' + is_private_item.stored_value);
});

run_test('create_pills', () => {
    let input_pill_create_called = false;

    input_pill.create = function () {
        input_pill_create_called = true;
        return {dummy: 'dummy'};
    };

    const pills = search_pill.create_pills({});
    assert(input_pill_create_called);
    assert.deepEqual(pills, {dummy: 'dummy'});
});

run_test('create_item', () => {
    people.add_active_user(steven);

    function test_pill_display(search_string, expected_string) {
        const term = Filter.parse(search_string);
        assert.equal(search_pill.get_display_value(term, search_string), expected_string);
    }

    test_pill_display('stream: Devel', '# Devel');
    test_pill_display('topic: testing', '> testing');
    test_pill_display('abc', 'search: abc');
    test_pill_display('has:link', 'has:link');

    const person_pills = ['sender: ', 'from: ', 'pm-with: ', 'group-pm-with: '];
    for (const prefix of person_pills) {
        test_pill_display(prefix + steven.email, prefix + steven.full_name);
    }

});
