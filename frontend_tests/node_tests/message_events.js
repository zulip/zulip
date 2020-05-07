zrequire('message_events');
zrequire('message_store');
zrequire('muting');
zrequire('people');
zrequire('recent_senders');
zrequire('stream_data');
zrequire('stream_topic_history');
zrequire('unread');

set_global('alert_words', {});
set_global('compose_state', {});
set_global('condense', {});
set_global('current_msg_list', {});
set_global('home_msg_list', {});
set_global('message_edit', {});
set_global('message_list', {});
set_global('narrow_state', {});
set_global('notifications', {});
set_global('page_params', {});
set_global('pm_list', {});
set_global('stream_list', {});
set_global('unread_ui', {});

alert_words.process_message = () => {};
compose_state.stream_name = () => {};
home_msg_list.update_muting_and_rerender = () => {};
narrow_state.filter = () => {};

const alice = {
    email: 'alice@example.com',
    user_id: 32,
    full_name: 'Alice Patel',
};

people.add(alice);

const denmark = {
    subscribed: false,
    name: 'Denmark',
    stream_id: 101,
};
stream_data.add_sub(denmark);

const original_message = {
    id: 111,
    display_recipient: denmark.name,
    flags: ['mentioned'],
    sender_id: alice.user_id,
    stream_id: denmark.stream_id,
    topic: 'lunch-old',
    type: 'stream',
};

const side_effects = [
    'condense.un_cache_message_content_height',
    'message_edit.end_message_row_edit',
    'notifications.received_messages',
    'unread_ui.update_unread_counts',
    'stream_list.update_streams_sidebar',
    'pm_list.update_private_messages',
];

function test_helper(side_effects) {
    const events = [];

    for (const side_effect of side_effects) {
        const parts = side_effect.split('.');
        const module = parts[0];
        const field = parts[1];

        global[module][field] = () => {
            events.push(side_effect);
        };
    }

    const self = {};

    self.verify = () => {
        assert.deepEqual(side_effects, events);
    };

    return self;
}

run_test('update_topic', () => {

    message_store.add_message_metadata(original_message);
    message_store.set_message_booleans(original_message);

    assert.equal(original_message.mentioned, true);
    assert.equal(original_message.unread, true);
    assert.deepEqual(
        stream_topic_history.get_recent_topic_names(denmark.stream_id),
        ['lunch-old']
    );

    unread.update_message_for_mention(original_message);
    assert(unread.unread_mentions_counter.has(original_message.id));

    const events = [
        {
            flags: [],
            message_id: 111,
            message_ids: [111],
            orig_subject: 'lunch-old',
            stream_id: denmark.stream_id,
            subject: 'lunch',
        },
    ];

    stream_data.get_sub_by_id = function (stream_id) {
        assert(stream_id, 101);
        return {name: denmark.name};
    };

    unread.update_unread_topics = function (msg, event) {
        assert(msg.id, 111);
        assert(event.message_id, 111);
    };

    current_msg_list.get_row = (message_id) => {
        assert.equal(message_id, 111);
        return ['row-stub'];
    };

    let rendered_msg;

    alert_words.process_message = (msg) => {
        rendered_msg = msg;
    };

    const helper = test_helper(side_effects);

    page_params.realm_allow_edit_history = false;
    message_list.narrowed = 'stub-to-ignore';

    // TEST THIS:
    message_events.update_messages(events);

    assert(!unread.unread_mentions_counter.has(original_message.id));

    helper.verify();

    assert.deepEqual(rendered_msg,  {
        alerted: false,
        collapsed: false,
        display_recipient: 'Denmark',
        historical: false,
        id: 111,
        is_stream: true,
        last_edit_timestamp: undefined,
        mentioned: false,
        mentioned_me_directly: false,
        reactions: [],
        reply_to: 'alice@example.com',
        sender_email: 'alice@example.com',
        sender_full_name: 'Alice Patel',
        sender_id: 32,
        sent_by_me: false,
        starred: false,
        stream: 'Denmark',
        stream_id: 101,
        topic: 'lunch',
        topic_links: undefined,
        type: 'stream',
        unread: true,
    });

});

run_test('update_messages', () => {

    message_store.add_message_metadata(original_message);
    message_store.set_message_booleans(original_message);

    assert.equal(original_message.unread, true);
    assert.deepEqual(
        stream_topic_history.get_recent_topic_names(denmark.stream_id),
        ['lunch']
    );

    const events = [
        {
            message_id: original_message.id,
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

    let rendered_mgs;

    current_msg_list.view.rerender_messages = (msgs_to_rerender, message_content_edited) => {
        rendered_mgs = msgs_to_rerender;
        assert.equal(message_content_edited, true);
    };

    const helper = test_helper(side_effects);

    page_params.realm_allow_edit_history = false;
    message_list.narrowed = 'stub-to-ignore';

    // TEST THIS:
    message_events.update_messages(events);

    assert(!unread.unread_mentions_counter.has(original_message.id));

    helper.verify();

    assert.deepEqual(rendered_mgs,  [
        {
            alerted: false,
            collapsed: false,
            content: '<b>new content</b>',
            display_recipient: denmark.name,
            historical: false,
            id: 111,
            is_stream: true,
            last_edit_timestamp: undefined,
            mentioned: false,
            mentioned_me_directly: false,
            raw_content: '**new content**',
            reactions: [],
            reply_to: alice.email,
            sender_email: alice.email,
            sender_full_name: alice.full_name,
            sender_id: 32,
            sent_by_me: false,
            starred: false,
            stream: denmark.name,
            stream_id: denmark.stream_id,
            topic: 'lunch',
            topic_links: undefined,
            type: 'stream',
            unread: true,
        },
    ]);

});
