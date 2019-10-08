set_global('$', global.make_zjquery());

const _people = {
    small_avatar_url_for_person: function () {
        return 'http://example.com/example.png';
    },
};

set_global('people', _people);
zrequire('util');

zrequire('compose_pm_pill');
zrequire('input_pill');
zrequire('user_pill');

var pills = {
    pill: {},
};

run_test('pills', () => {
    var othello = {
        user_id: 1,
        email: 'othello@example.com',
        full_name: 'Othello',
    };

    var iago = {
        email: 'iago@zulip.com',
        user_id: 2,
        full_name: 'Iago',
    };

    var hamlet = {
        email: 'hamlet@example.com',
        user_id: 3,
        full_name: 'Hamlet',
    };

    people.get_realm_persons = function () {
        return [iago, othello, hamlet];
    };

    var recipient_stub = $("#private_message_recipient");
    var pill_container_stub = $('.pill-container[data-before="You and"]');
    recipient_stub.set_parent(pill_container_stub);
    var create_item_handler;

    var all_pills = {};

    pills.appendValidatedData = function (item) {
        var id = item.user_id;
        assert.equal(all_pills[id], undefined);
        all_pills[id] = item;
    };
    pills.items = function () {
        return _.values(all_pills);
    };

    var text_cleared;
    pills.clear_text = function () {
        text_cleared = true;
    };

    var pills_cleared;
    pills.clear = function () {
        pills_cleared = true;
        pills = {
            pill: {},
        };
        all_pills = {};
    };

    var appendValue_called;
    pills.appendValue = function (value) {
        appendValue_called = true;
        assert.equal(value, 'othello@example.com');
        this.appendValidatedData(othello);
    };

    var get_by_email_called = false;
    people.get_by_email = function (user_email) {
        get_by_email_called = true;
        if (user_email === iago.email) {
            return iago;
        }
        if (user_email === othello.email) {
            return othello;
        }
    };

    var get_person_from_user_id_called = false;
    people.get_person_from_user_id = function (id) {
        get_person_from_user_id_called = true;
        if (id === othello.user_id) {
            return othello;
        }
        assert.equal(id, 3);
        return hamlet;
    };

    function test_create_item(handler) {
        (function test_rejection_path() {
            var item = handler(othello.email, pills.items());
            assert(get_by_email_called);
            assert.equal(item, undefined);
        }());

        (function test_success_path() {
            get_by_email_called = false;
            var res = handler(iago.email, pills.items());
            assert(get_by_email_called);
            assert.equal(typeof res, 'object');
            assert.equal(res.user_id, iago.user_id);
            assert.equal(res.display_value, iago.full_name);
        }());
    }

    function input_pill_stub(opts) {
        assert.equal(opts.container, pill_container_stub);
        create_item_handler = opts.create_item_from_text;
        assert(create_item_handler);
        return pills;
    }

    input_pill.create = input_pill_stub;

    compose_pm_pill.initialize();
    assert(compose_pm_pill.widget);

    compose_pm_pill.set_from_typeahead(othello);
    compose_pm_pill.set_from_typeahead(hamlet);

    var user_ids = compose_pm_pill.get_user_ids();
    assert.deepEqual(user_ids, [othello.user_id, hamlet.user_id]);

    var user_ids_string = compose_pm_pill.get_user_ids_string();
    assert.equal(user_ids_string, '1,3');

    var emails = compose_pm_pill.get_emails();
    assert.equal(emails, 'othello@example.com,hamlet@example.com');

    var items = compose_pm_pill.get_typeahead_items();
    assert.deepEqual(items, [{email: 'iago@zulip.com', user_id: 2, full_name: 'Iago'}]);

    test_create_item(create_item_handler);

    compose_pm_pill.set_from_emails('othello@example.com');
    assert(compose_pm_pill.widget);

    assert(get_person_from_user_id_called);
    assert(pills_cleared);
    assert(appendValue_called);
    assert(text_cleared);
});

run_test('has_unconverted_data', () => {
    compose_pm_pill.widget = {
        is_pending: () => true,
    };

    // If the pill itself has pending data, we have unconverted
    // data.
    assert.equal(compose_pm_pill.has_unconverted_data(), true);

    compose_pm_pill.widget = {
        is_pending: () => false,
        items: () => [{user_id: 99}],
    };

    // Our pill is complete and all items containt user_id, so
    // we do NOT have unconverted data.
    assert.equal(compose_pm_pill.has_unconverted_data(), false);

    compose_pm_pill.widget = {
        is_pending: () => false,
        items: () => [{user_id: 99}, {email: 'random@mit.edu'}],
    };

    // One of our items only knows email (as in a bridge-with-zephyr
    // scenario where we might not have registered the user yet), so
    // we have some unconverted data.
    assert.equal(compose_pm_pill.has_unconverted_data(), true);
});
