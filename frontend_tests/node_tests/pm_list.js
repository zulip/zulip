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

set_global('unread', {});

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
