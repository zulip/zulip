zrequire('message_events');
zrequire('message_store');
zrequire('people');
zrequire('util');

set_global('alert_words', {});
set_global('condense', {});
set_global('current_msg_list', {});
set_global('message_edit', {});
set_global('message_list', {});
set_global('notifications', {});
set_global('page_params', {});
set_global('pm_list', {});
set_global('stream_list', {});
set_global('unread_ui', {});

alert_words.process_message = () => {};

const alice = {
    email: 'alice@example.com',
    user_id: 32,
    full_name: 'Alice Patel',
};

people.add(alice);

function test_helper(side_effects) {
    const events = [];

    _.each(side_effects, (side_effect) => {
        const parts = side_effect.split('.');
        const module = parts[0];
        const field = parts[1];

        global[module][field] = () => {
            events.push(side_effect);
        };
    });

    const self = {};

    self.verify = () => {
        assert.deepEqual(side_effects, events);
    };

    return self;
}

run_test('update_messages', () => {
    const original_message = {
        id: 111,
        sender_id: alice.user_id,
    };

    message_store.add_message_metadata(original_message);

    const events = [
        {
            message_id: 111,
            flags: [],
            orig_content: 'old stuff',
            content: '**new content**',
            rendered_content: '<b>new content</b>',
        },
    ];

    current_msg_list.get_row = (message_id) => {
        assert.equal(message_id, 111);
        return ['row-stub'];
    };
    current_msg_list.view = {};

    var rendered_mgs;

    current_msg_list.view.rerender_messages = (msgs_to_rerender, message_content_edited) => {
        rendered_mgs = msgs_to_rerender;
        assert.equal(message_content_edited, true);
    };

    const side_effects = [
        'condense.un_cache_message_content_height',
        'message_edit.end',
        'notifications.received_messages',
        'unread_ui.update_unread_counts',
        'stream_list.update_streams_sidebar',
        'pm_list.update_private_messages',
    ];

    const helper = test_helper(side_effects);

    page_params.realm_allow_edit_history = false;
    message_list.narrowed = 'stub-to-ignore';

    // TEST THIS:
    message_events.update_messages(events);

    helper.verify();

    assert.deepEqual(rendered_mgs,  [
        {
            alerted: false,
            content: '<b>new content</b>',
            id: 111,
            last_edit_timestamp: undefined,
            mentioned: false,
            mentioned_me_directly: false,
            raw_content: '**new content**',
            reactions: [],
            sender_email: 'alice@example.com',
            sender_full_name: 'Alice Patel',
            sender_id: 32,
            sent_by_me: false,
            topic: undefined,
        },
    ]);

});
