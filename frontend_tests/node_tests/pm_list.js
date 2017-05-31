set_global('$', global.make_zjquery());

add_dependencies({
    Handlebars: 'handlebars',
    templates: 'js/templates',
    hash_util: 'js/hash_util',
    hashchange: 'js/hashchange',
    narrow: 'js/narrow',
    people: 'js/people',
});

set_global('message_store', {
    recent_private_messages: new global.Array(),
});

set_global('narrow_state', {});
set_global('resize', {
    resize_stream_filters_container: function () {},
});
set_global('stream_popover', {
    hide_topic_popover: function () {},
});
set_global('unread', {});
set_global('unread_ui', {});

// TODO: move pm_list-related tests to their own module
var pm_list = require('js/pm_list.js');

global.compile_template('sidebar_private_message_list');

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
global.people.add_in_realm(alice);
global.people.add_in_realm(bob);
global.people.add_in_realm(me);
global.people.initialize_current_user(me.user_id);

(function test_build_private_messages_list() {
    var active_conversation = "alice@zulip.com,bob@zulip.com";
    var max_conversations = 5;


    var conversations = {user_ids_string: '101,102',
                         timestamp: 0 };
    global.message_store.recent_private_messages.push(conversations);

    global.unread.num_unread_for_person = function () {
        return 1;
    };

    var template_data;

    global.templates.render = function (template_name, data) {
        assert.equal(template_name, 'sidebar_private_message_list');
        template_data = data;
    };

    pm_list._build_private_messages_list(active_conversation, max_conversations);

    var expected_data = {
        messages: [
            {
                recipients: 'Alice, Bob',
                user_ids_string: '101,102',
                unread: 1,
                is_zero: false,
                zoom_out_hide: false,
                url: '#narrow/pm-with/101,102-group',
            },
        ],
        zoom_class: 'zoomed-out',
        want_show_more_messages_links: false,
    };

    assert.deepEqual(template_data, expected_data);

}());

(function test_expand_and_update_private_messages() {
    var collapsed;
    $('ul.expanded_private_messages').remove = function () {
        collapsed = true;
    };

    global.templates.render = function (template_name) {
        assert.equal(template_name, 'sidebar_private_message_list');
        return 'fake-dom-for-pm-list';
    };

    var private_li = $("#global_filters > li[data-name='private']");
    var alice_li = $('alice-li-stub');
    var bob_li = $('bob-li-stub');

    private_li.add_child("li[data-user-ids-string='101']", alice_li);
    private_li.add_child("li[data-user-ids-string='102']", bob_li);

    var dom;
    private_li.append = function (html) {
        dom = html;
    };

    pm_list.expand([alice.email]);
    assert.equal(dom, 'fake-dom-for-pm-list');
    assert(collapsed);
    assert(alice_li.hasClass('active-sub-filter'));

    // Next, simulate clicking on Bob.
    narrow_state.active = function () { return true; };

    narrow_state.filter = function () {
        return {
            operands: function (operand) {
                if (operand === 'is') {
                    return 'private';
                }
                assert.equal(operand, 'pm-with');
                return [bob.email];
            },
        };
    };

    collapsed = false;

    pm_list.update_private_messages();

    assert(collapsed);
    assert(bob_li.hasClass('active-sub-filter'));
}());

(function test_update_dom_with_unread_counts() {
    var total_value = $('total-value-stub');
    var total_count = $('total-count-stub');
    var private_li = $("#global_filters > li[data-name='private']");
    private_li.add_child('.count', total_count);
    total_count.add_child('.value', total_value);

    var child_value = $('child-value-stub');
    var child_count = $('child-count-stub');
    var child_li = $('child-li-stub');
    private_li.add_child("li[data-user-ids-string='101,102']", child_li);
    child_li.add_child('.private_message_count', child_count);
    child_count.add_child('.value', child_value);

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

    unread_ui.animate_private_message_changes = function () {};

    pm_list.update_dom_with_unread_counts(counts);

    assert(toggle_button_set);
    assert.equal(child_value.text(), '7');
    assert.equal(total_value.text(), '10');
}());
