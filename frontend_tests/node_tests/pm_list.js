set_global('$', global.make_zjquery());

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

var alice = {
    email: 'alice@zulip.com',
    user_id: 101,
    full_name: 'Alice',
};
var bob = {
    email: 'bob@zulip.com',
    user_id: 102,
    full_name: 'Bob',
};
var me = {
    email: 'me@zulip.com',
    user_id: 103,
    full_name: 'Me Myself',
};
var bot_test = {
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

run_test('get_conversation_li', () => {
    var test_conversation = 'foo@example.com,bar@example.com'; // people.js
    pm_list.get_conversation_li(test_conversation);
});

run_test('close', () => {
    var collapsed;
    $('#private-container').empty = function () {
        collapsed = true;
    };
    pm_list.close();
    assert(collapsed);
});

run_test('build_private_messages_list', () => {
    var active_conversation_1 = "alice@zulip.com,bob@zulip.com";
    var active_conversation_2 = 'me@zulip.com,alice@zulip.com';
    var max_conversations = 5;

    var user_ids_string = '101,102';
    var timestamp = 0;
    pm_conversations.recent.insert(user_ids_string, timestamp);

    global.unread.num_unread_for_person = function () {
        return 1;
    };

    var template_data;

    global.stub_templates(function (template_name, data) {
        assert.equal(template_name, 'sidebar_private_message_list');
        template_data = data;
    });

    pm_list._build_private_messages_list(active_conversation_1, max_conversations);

    var expected_data = {
        messages: [
            {
                recipients: 'Alice, Bob',
                user_ids_string: '101,102',
                unread: 1,
                is_zero: false,
                url: '#narrow/pm-with/101,102-group',
                user_circle_class: 'user_circle_fraction',
                fraction_present: false,
                is_group: true,
            },
        ],
    };

    assert.deepEqual(template_data, expected_data);

    max_conversations = 0;
    global.unread.num_unread_for_person = function () {
        return 0;
    };
    pm_list._build_private_messages_list(active_conversation_2, max_conversations);
    expected_data.messages[0].unread = 0;
    expected_data.messages[0].is_zero = true;
    assert.deepEqual(template_data, expected_data);

    pm_list.initialize();
    pm_list._build_private_messages_list(active_conversation_2, max_conversations);
    assert.deepEqual(template_data, expected_data);
});

run_test('build_private_messages_list_bot', () => {
    var active_conversation_1 = 'outgoingwebhook@zulip.com';
    var max_conversations = 5;

    var user_ids_string = '314';
    var timestamp = 0;
    pm_conversations.recent.insert(user_ids_string, timestamp);

    global.unread.num_unread_for_person = function () {
        return 1;
    };

    var template_data;
    global.stub_templates(function (template_name, data) {
        assert.equal(template_name, 'sidebar_private_message_list');
        template_data = data;
    });

    pm_list._build_private_messages_list(active_conversation_1, max_conversations);
    var expected_data = {
        messages: [
            {
                recipients: 'Outgoing webhook',
                user_ids_string: '314',
                unread: 1,
                is_zero: false,
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
                url: '#narrow/pm-with/101,102-group',
                user_circle_class: 'user_circle_fraction',
                fraction_present: false,
                is_group: true,
            },
        ],
    };

    assert.deepEqual(template_data, expected_data);
});

run_test('expand_and_update_private_messages', () => {
    global.stub_templates(function (template_name) {
        assert.equal(template_name, 'sidebar_private_message_list');
        return 'fake-dom-for-pm-list';
    });

    var private_li = $(".top_left_private_messages");
    var alice_li = $.create('alice-li-stub');
    var bob_li = $.create('bob-li-stub');

    private_li.set_find_results("li[data-user-ids-string='101']", alice_li);
    private_li.set_find_results("li[data-user-ids-string='102']", bob_li);

    var dom;
    $('#private-container').html = function (html) {
        dom = html;
    };

    pm_list.expand([alice.email, bob.email]);
    assert.equal(dom, 'fake-dom-for-pm-list');
    assert(!alice_li.hasClass('active-sub-filter'));

    pm_list.expand([alice.email]);
    assert.equal(dom, 'fake-dom-for-pm-list');
    assert(alice_li.hasClass('active-sub-filter'));

    pm_list.expand([]);
    assert.equal(dom, 'fake-dom-for-pm-list');

    // Next, simulate clicking on Bob.
    narrow_state.active = function () { return true; };

    narrow_state.filter = function () {
        return {
            operands: function (operand) {
                if (operand === 'is') {
                    return 'private';
                }
                assert.equal(operand, 'pm-with');
                return [bob.email, alice.email];
            },
        };
    };

    pm_list.update_private_messages();

    assert(!bob_li.hasClass('active-sub-filter'));

    narrow_state.filter = function () {
        return {
            operands: function (operand) {
                if (operand === 'is') {
                    return ['private'];
                }
                assert.equal(operand, 'pm-with');
                return [];
            },
        };
    };

    pm_list.update_private_messages();

    assert(!bob_li.hasClass('active-sub-filter'));

    narrow_state.filter = function () {
        return {
            operands: function (operand) {
                if (operand === 'is') {
                    return ['private'];
                }
                assert.equal(operand, 'pm-with');
                return [bob.email];
            },
        };
    };

    pm_list.update_private_messages();

    assert(bob_li.hasClass('active-sub-filter'));

    narrow_state.active = function () { return false; };
    pm_list.update_private_messages();

});

run_test('update_dom_with_unread_counts', () => {
    var total_value = $.create('total-value-stub');
    var total_count = $.create('total-count-stub');
    var private_li = $(".top_left_private_messages");
    private_li.set_find_results('.count', total_count);
    total_count.set_find_results('.value', total_value);

    var child_value = $.create('child-value-stub');
    var child_count = $.create('child-count-stub');
    var child_li = $.create('child-li-stub');
    private_li.set_find_results("li[data-user-ids-string='101,102']", child_li);
    child_li.set_find_results('.private_message_count', child_count);
    child_count.set_find_results('.value', child_value);

    child_value.length = 1;
    child_count.length = 1;

    var pm_count = new Dict();
    var user_ids_string = '101,102';
    pm_count.set(user_ids_string, 7);

    var counts = {
        private_message_count: 10,
        pm_count: pm_count,
    };

    var toggle_button_set;
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

    var pm_li = pm_list.get_conversation_li("alice@zulip.com,bob@zulip.com");
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
