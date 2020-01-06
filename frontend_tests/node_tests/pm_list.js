set_global('$', global.make_zjquery());

const Dict = zrequire('dict').Dict;

set_global('narrow_state', {});
set_global('resize', {
    resize_stream_filters_container: function () {},
});
set_global('ui', {
    get_content_element: element => element,
});
set_global('stream_popover', {
    hide_topic_popover: function () {},
});
set_global('unread', {});
set_global('unread_ui', {});
set_global('blueslip', global.make_zblueslip());
set_global('popovers', {
    hide_all: function () {},
});

zrequire('user_status');
zrequire('presence');
zrequire('buddy_data');
zrequire('hash_util');
set_global('Handlebars', global.make_handlebars());
zrequire('people');
zrequire('pm_conversations');
zrequire('pm_list');

const alice = {
    email: 'alice@zulip.com',
    user_id: 101,
    full_name: 'Alice',
};
const bob = {
    email: 'bob@zulip.com',
    user_id: 102,
    full_name: 'Bob',
};
const me = {
    email: 'me@zulip.com',
    user_id: 103,
    full_name: 'Me Myself',
};
const bot_test = {
    email: 'outgoingwebhook@zulip.com',
    user_id: 314,
    full_name: "Outgoing webhook",
    is_admin: false,
    is_bot: true,
};
global.people.add_in_realm(alice);
global.people.add_in_realm(bob);
global.people.add_in_realm(me);
global.people.add_in_realm(bot_test);
global.people.initialize_current_user(me.user_id);

run_test('close', () => {
    let collapsed;
    $('#private-container').empty = function () {
        collapsed = true;
    };
    pm_list.close();
    assert(collapsed);
});

run_test('build_private_messages_list', () => {
    const timestamp = 0;
    pm_conversations.recent.insert([101, 102], timestamp);

    global.unread.num_unread_for_person = function () {
        return 1;
    };

    let template_data;

    global.stub_templates(function (template_name, data) {
        assert.equal(template_name, 'sidebar_private_message_list');
        template_data = data;
    });

    narrow_state.filter = () => {};
    pm_list._build_private_messages_list();

    const expected_data = {
        messages: [
            {
                recipients: 'Alice, Bob',
                user_ids_string: '101,102',
                unread: 1,
                is_zero: false,
                is_active: false,
                url: '#narrow/pm-with/101,102-group',
                user_circle_class: 'user_circle_fraction',
                fraction_present: undefined,
                is_group: true,
            },
        ],
    };

    assert.deepEqual(template_data, expected_data);

    global.unread.num_unread_for_person = function () {
        return 0;
    };
    pm_list._build_private_messages_list();
    expected_data.messages[0].unread = 0;
    expected_data.messages[0].is_zero = true;
    assert.deepEqual(template_data, expected_data);

    pm_list.initialize();
    pm_list._build_private_messages_list();
    assert.deepEqual(template_data, expected_data);
});

run_test('build_private_messages_list_bot', () => {
    const timestamp = 0;
    pm_conversations.recent.insert([314], timestamp);

    global.unread.num_unread_for_person = function () {
        return 1;
    };

    let template_data;
    global.stub_templates(function (template_name, data) {
        assert.equal(template_name, 'sidebar_private_message_list');
        template_data = data;
    });

    pm_list._build_private_messages_list();
    const expected_data = {
        messages: [
            {
                recipients: 'Outgoing webhook',
                user_ids_string: '314',
                unread: 1,
                is_zero: false,
                is_active: false,
                url: '#narrow/pm-with/314-outgoingwebhook',
                user_circle_class: 'user_circle_green',
                fraction_present: undefined,
                is_group: false,
            },
            {
                recipients: 'Alice, Bob',
                user_ids_string: '101,102',
                unread: 1,
                is_zero: false,
                is_active: false,
                url: '#narrow/pm-with/101,102-group',
                user_circle_class: 'user_circle_fraction',
                fraction_present: undefined,
                is_group: true,
            },
        ],
    };

    assert.deepEqual(template_data, expected_data);
});

run_test('update_dom_with_unread_counts', () => {
    const total_value = $.create('total-value-stub');
    const total_count = $.create('total-count-stub');
    const private_li = $(".top_left_private_messages");
    private_li.set_find_results('.count', total_count);
    total_count.set_find_results('.value', total_value);

    const child_value = $.create('child-value-stub');
    const child_count = $.create('child-count-stub');
    const child_li = $.create('child-li-stub');
    private_li.set_find_results("li[data-user-ids-string='101,102']", child_li);
    child_li.set_find_results('.private_message_count', child_count);
    child_count.set_find_results('.value', child_value);

    child_value.length = 1;
    child_count.length = 1;

    const pm_count = new Dict();
    const user_ids_string = '101,102';
    pm_count.set(user_ids_string, 7);

    let counts = {
        private_message_count: 10,
        pm_count: pm_count,
    };

    let toggle_button_set;
    unread_ui.set_count_toggle_button = function (elt, count) {
        toggle_button_set = true;
        assert.equal(count, 10);
    };

    pm_list.update_dom_with_unread_counts(counts);

    assert(toggle_button_set);
    assert.equal(child_value.text(), '7');
    assert.equal(total_value.text(), '10');

    pm_count.set(user_ids_string, 0);
    counts = {
        private_message_count: 0,
        pm_count: pm_count,
    };
    toggle_button_set = false;
    unread_ui.set_count_toggle_button = function (elt, count) {
        toggle_button_set = true;
        assert.equal(count, 0);
    };
    pm_list.update_dom_with_unread_counts(counts);

    assert(toggle_button_set);
    assert.equal(child_value.text(), '');
    assert.equal(total_value.text(), '');

    const pm_li = pm_list.get_li_for_user_ids_string("101,102");
    pm_li.find = function (sel) {
        assert.equal(sel, '.private_message_count');
        return {find: function (sel) {
            assert.equal(sel, '.value');
            return [];
        }};
    };
    pm_list.update_dom_with_unread_counts(counts);
    assert(toggle_button_set);
    assert.equal(child_value.text(), '');
    assert.equal(total_value.text(), '');
});

run_test('get_active_user_ids_string', () => {
    narrow_state.filter = () => {};

    assert.equal(
        pm_list.get_active_user_ids_string(),
        undefined);

    function set_filter_result(emails) {
        narrow_state.filter = () => {
            return {
                operands: (operand) => {
                    assert.equal(operand, 'pm-with');
                    return emails;
                },
            };
        };
    }

    set_filter_result([]);
    assert.equal(
        pm_list.get_active_user_ids_string(),
        undefined);

    set_filter_result(['bob@zulip.com,alice@zulip.com']);
    assert.equal(
        pm_list.get_active_user_ids_string(),
        '101,102');
});

run_test('is_all_privates', () => {
    narrow_state.filter = () => {};

    assert.equal(
        pm_list.is_all_privates(),
        false);

    narrow_state.filter = () => {
        return {
            operands: (operand) => {
                assert.equal(operand, 'pm-with');
                return ['alice@zulip.com'];
            },
        };
    };
    assert.equal(
        pm_list.is_all_privates(),
        false);

    narrow_state.filter = () => {
        return {
            operands: (operand) => {
                if (operand === 'pm-with') {
                    return [];
                }
                assert.equal(operand, 'is');
                return ['private', 'starred'];
            },
        };
    };

    assert.equal(
        pm_list.is_all_privates(),
        true);
});

function with_fake_list(f) {
    const orig = pm_list._build_private_messages_list;
    pm_list._build_private_messages_list = () => {
        return 'PM_LIST_CONTENTS';
    };
    f();
    pm_list._build_private_messages_list = orig;
}

run_test('expand', () => {
    with_fake_list(() => {
        let html_inserted;

        $('#private-container').html = function (html) {
            assert.equal(html, 'PM_LIST_CONTENTS');
            html_inserted = true;
        };
        pm_list.expand();

        assert(html_inserted);
    });
});

run_test('update_private_messages', () => {
    narrow_state.active = () => true;

    with_fake_list(() => {
        let html_inserted;

        $('#private-container').html = function (html) {
            assert.equal(html, 'PM_LIST_CONTENTS');
            html_inserted = true;
        };

        const orig_is_all_privates = pm_list.is_all_privates;
        pm_list.is_all_privates = () => true;

        pm_list.update_private_messages();

        assert(html_inserted);
        assert($(".top_left_private_messages").hasClass('active-filter'));

        pm_list.is_all_privates = orig_is_all_privates;
    });
});

run_test('ensure coverage', () => {
    // These aren't rigorous; they just cover cases
    // where functions early exit.
    narrow_state.active = () => false;
    pm_list.rebuild_recent = () => {
        throw Error('we should not call rebuild_recent');
    };
    pm_list.update_private_messages();
});
