zrequire('muting');
zrequire('people');
zrequire('stream_data');
zrequire('unread');

set_global('blueslip', {});
set_global('page_params', {});
set_global('feature_flags', {
    load_server_counts: true,
});
set_global('narrow_state', {});
set_global('current_msg_list', {});
set_global('home_msg_list', {});
set_global('message_store', {});

var me = {
    email: 'me@example.com',
    user_id: 30,
    full_name: 'Me Myself',
};
people.add(me);
people.initialize_current_user(me.user_id);

var zero_counts = {
    private_message_count: 0,
    home_unread_messages: 0,
    mentioned_message_count: 0,
    stream_count: new Dict(),
    topic_count: new Dict(),
    pm_count: new Dict(),
};

(function test_empty_counts_while_narrowed() {
    narrow_state.active = function () {
        return true;
    };
    current_msg_list.all_messages = function () {
        return [];
    };

    var counts = unread.get_counts();
    assert.deepEqual(counts, zero_counts);
}());

(function test_empty_counts_while_home() {
    narrow_state.active = function () {
        return false;
    };
    current_msg_list.all_messages = function () {
        return [];
    };

    var counts = unread.get_counts();
    assert.deepEqual(counts, zero_counts);
}());

(function test_changing_subjects() {
    // Summary: change the subject of a message from 'lunch'
    // to 'dinner' using update_unread_topics().
    var count = unread.num_unread_for_topic('social', 'lunch');
    assert.equal(count, 0);

    var stream_id = 100;
    var wrong_stream_id = 110;

    var message = {
        id: 15,
        type: 'stream',
        stream_id: stream_id,
        subject: 'luNch',
        unread: true,
    };

    var other_message = {
        id: 16,
        type: 'stream',
        stream_id: stream_id,
        subject: 'lunCH',
        unread: true,
    };

    assert.deepEqual(unread.get_unread_message_ids([15, 16]), []);
    assert.deepEqual(unread.get_unread_messages([message, other_message]), []);

    unread.process_loaded_messages([message, other_message]);

    assert.deepEqual(unread.get_unread_message_ids([15, 16]), [15, 16]);
    assert.deepEqual(
        unread.get_unread_messages([message, other_message]),
        [message, other_message]
    );

    count = unread.num_unread_for_topic(stream_id, 'Lunch');
    assert.equal(count, 2);
    assert(unread.topic_has_any_unread(stream_id, 'lunch'));
    assert(!unread.topic_has_any_unread(wrong_stream_id, 'lunch'));
    assert(!unread.topic_has_any_unread(stream_id, 'NOT lunch'));

    count = unread.num_unread_for_topic(stream_id, 'NOT lunch');
    assert.equal(count, 0);

    var event = {
        subject: 'dinner',
    };

    unread.update_unread_topics(message, event);

    count = unread.num_unread_for_topic(stream_id, 'lUnch');
    assert.equal(count, 1);

    count = unread.num_unread_for_topic(stream_id, 'dinner');
    assert.equal(count, 1);

    event = {
        subject: 'snack',
    };

    unread.update_unread_topics(other_message, event);

    count = unread.num_unread_for_topic(stream_id, 'lunch');
    assert.equal(count, 0);
    assert(!unread.topic_has_any_unread(stream_id, 'lunch'));
    assert(!unread.topic_has_any_unread(wrong_stream_id, 'lunch'));

    count = unread.num_unread_for_topic(stream_id, 'snack');
    assert.equal(count, 1);
    assert(unread.topic_has_any_unread(stream_id, 'snack'));
    assert(!unread.topic_has_any_unread(wrong_stream_id, 'snack'));

    // Test defensive code.  Trying to update a message we don't know
    // about should be a no-op.
    event = {
        subject: 'brunch',
    };
    unread.update_unread_topics(other_message, event);

    // Update a message that was never marked as unread.
    var sticky_message = {
        id: 17,
        type: 'stream',
        stream_id: stream_id,
        subject: 'sticky',
        unread: true,
    };

    var message_dict = new Dict();
    message_dict.set(message.id, message);
    message_dict.set(other_message.id, other_message);
    message_dict.set(sticky_message.id, sticky_message);

    message_store.get = function (msg_id) {
        return message_dict.get(msg_id);
    };

    unread.process_loaded_messages([sticky_message]);
    count = unread.num_unread_for_topic(stream_id, 'sticky');
    assert.equal(count, 1);
    assert(sticky_message.unread);

    unread.mark_as_read(sticky_message.id);
    count = unread.num_unread_for_topic(stream_id, 'sticky');
    assert.equal(count, 0);
    assert(!sticky_message.unread);

    unread.update_unread_topics(sticky_message, {subject: 'sticky'});
    count = unread.num_unread_for_topic(stream_id, 'sticky');
    assert.equal(count, 0);

    // cleanup
    unread.mark_as_read(message.id);
    count = unread.num_unread_for_topic(stream_id, 'dinner');
    assert.equal(count, 0);

    unread.mark_as_read(other_message.id);
    count = unread.num_unread_for_topic(stream_id, 'snack');
    assert.equal(count, 0);

    // test coverage
    unread.update_unread_topics(sticky_message, {});
}());

stream_data.get_stream_id = function () {
    return 999;
};

(function test_muting() {
    stream_data.is_subscribed = function () {
        return true;
    };

    stream_data.in_home_view = function () {
        return true;
    };

    unread.declare_bankruptcy();

    var stream_id = 101;
    var unknown_stream_id = 555;

    stream_data.get_sub_by_id = function (stream_id) {
        if (stream_id === 101) {
            return {name: 'social'};
        }
    };

    var message = {
        id: 15,
        type: 'stream',
        stream_id: stream_id,
        subject: 'test_muting',
        unread: true,
    };

    unread.process_loaded_messages([message]);
    var counts = unread.get_counts();
    assert.equal(counts.stream_count.get(stream_id), 1);
    assert.equal(counts.home_unread_messages, 1);
    assert.equal(unread.num_unread_for_stream(stream_id), 1);

    muting.add_muted_topic('social', 'test_muting');
    counts = unread.get_counts();
    assert.equal(counts.stream_count.get(stream_id), 0);
    assert.equal(counts.home_unread_messages, 0);
    assert.equal(unread.num_unread_for_stream(stream_id), 0);

    assert.equal(unread.num_unread_for_stream(unknown_stream_id), 0);
}());

(function test_num_unread_for_topic() {
    // Test the num_unread_for_topic() function using many
    // messages.
    unread.declare_bankruptcy();

    var stream_id = 301;
    var count = unread.num_unread_for_topic(stream_id, 'lunch');
    assert.equal(count, 0);

    var message = {
        type: 'stream',
        stream_id: stream_id,
        subject: 'lunch',
        unread: true,
    };

    var num_msgs = 500;
    var i;
    for (i = 0; i < num_msgs; i += 1) {
        message.id = i+1;
        unread.process_loaded_messages([message]);
    }

    count = unread.num_unread_for_topic(stream_id, 'lunch');
    assert.equal(count, num_msgs);

    for (i = 0; i < num_msgs; i += 1) {
        message.id = i+1;
        unread.mark_as_read(message.id);
    }

    count = unread.num_unread_for_topic(stream_id, 'lunch');
    assert.equal(count, 0);
}());


(function test_home_messages() {
    narrow_state.active = function () {
        return false;
    };
    stream_data.is_subscribed = function () {
        return true;
    };
    stream_data.in_home_view = function () {
        return true;
    };

    var stream_id = 401;

    stream_data.get_sub_by_id = function () {
        return {
            name: 'whatever',
        };
    };

    var message = {
        id: 15,
        type: 'stream',
        stream_id: stream_id,
        subject: 'lunch',
        unread: true,
    };

    home_msg_list.get = function (msg_id) {
        return (msg_id === '15') ? message : undefined;
    };

    var counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);

    unread.process_loaded_messages([message]);

    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 1);
    assert.equal(counts.stream_count.get(stream_id), 1);
    unread.mark_as_read(message.id);
    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);

    unread.process_loaded_messages([message]);
    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 1);

    // Now unsubscribe all our streams.
    stream_data.is_subscribed = function () {
        return false;
    };
    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);

}());

(function test_phantom_messages() {
    var message = {
        id: 999,
        type: 'stream',
        stream_id: 555,
        subject: 'phantom',
    };

    stream_data.get_sub_by_id = function () { return; };

    unread.mark_as_read(message.id);
    var counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);
}());

(function test_private_messages() {
    narrow_state.active = function () {
        return false;
    };
    stream_data.is_subscribed = function () {
        return true;
    };

    var counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);

    var anybody = {
        email: 'anybody@example.com',
        user_id: 999,
        full_name: 'Any Body',
    };
    people.add_in_realm(anybody);

    var message = {
        id: 15,
        type: 'private',
        display_recipient: [
            {user_id: anybody.user_id},
            {id: me.user_id},
        ],
        unread: true,
    };

    unread.process_loaded_messages([message]);

    counts = unread.get_counts();
    assert.equal(counts.private_message_count, 1);
    assert.equal(counts.pm_count.get('999'), 1);
    unread.mark_as_read(message.id);
    counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);
    assert.equal(counts.pm_count.get('999'), 0);
}());

(function test_num_unread_for_person() {
    var alice = {
        email: 'alice@example.com',
        user_id: 101,
        full_name: 'Alice',
    };
    people.add_in_realm(alice);

    var bob = {
        email: 'bob@example.com',
        user_id: 102,
        full_name: 'Bob',
    };
    people.add_in_realm(bob);

    assert.equal(unread.num_unread_for_person(alice.user_id), 0);
    assert.equal(unread.num_unread_for_person(bob.user_id), 0);

    var message = {
        id: 15,
        display_recipient: [{id: alice.user_id}],
        type: 'private',
        unread: true,
    };

    var read_message = {
        flags: ['read'],
    };
    unread.process_loaded_messages([message, read_message]);
    assert.equal(unread.num_unread_for_person(alice.user_id), 1);

    assert.equal(unread.num_unread_for_person(''), 0);
}());


(function test_mentions() {
    narrow_state.active = function () {
        return false;
    };
    stream_data.is_subscribed = function () {
        return true;
    };

    var counts = unread.get_counts();
    assert.equal(counts.mentioned_message_count, 0);

    var message = {
        id: 15,
        type: 'stream',
        stream_id: 999,
        subject: 'lunch',
        mentioned: true,
        unread:true,
    };

    unread.process_loaded_messages([message]);

    counts = unread.get_counts();
    assert.equal(counts.mentioned_message_count, 1);
    unread.mark_as_read(message.id);
    counts = unread.get_counts();
    assert.equal(counts.mentioned_message_count, 0);
}());

(function test_declare_bankruptcy() {
    var message = {
        id: 16,
        type: 'whatever',
        stream_id: 1999,
        subject: 'whatever',
        mentioned: true,
    };

    unread.process_loaded_messages([message]);

    unread.declare_bankruptcy();

    var counts = unread.get_counts();
    assert.deepEqual(counts, zero_counts);
}());

(function test_message_unread() {
    // Test some code that might be overly defensive, for line coverage sake.
    assert(!unread.message_unread(undefined));
    assert(unread.message_unread({unread: true}));
    assert(!unread.message_unread({unread: false}));
}());

(function test_server_counts() {
    // note that user_id 30 is "me"

    page_params.unread_msgs = {
        pms: [
            {
                sender_id: 101,
                unread_message_ids: [
                    31, 32, 60, 61, 62, 63,
                ],
            },
        ],
        huddles: [
            {
                user_ids_string: "4,6,30,101",
                unread_message_ids: [
                    34, 50,
                ],
            },
        ],
        streams: [
            {
                stream_id: 1,
                topic: "test",
                unread_message_ids: [
                    33, 35, 36,
                ],
            },
        ],
        mentions: [31, 34, 40, 41],
    };

    unread.declare_bankruptcy();
    unread.initialize();

    assert.equal(unread.num_unread_for_person('101'), 6);
    assert.equal(unread.num_unread_for_person('4,6,101'), 2);
    assert.equal(unread.num_unread_for_person('30'), 0);

    assert.equal(unread.num_unread_for_topic(0, 'bogus'), 0);
    assert.equal(unread.num_unread_for_topic(1, 'bogus'), 0);
    assert.equal(unread.num_unread_for_topic(1, 'test'), 3);

    assert.equal(unread.unread_mentions_counter.count(), 4);

    unread.mark_as_read(40);
    assert.equal(unread.unread_mentions_counter.count(), 3);

    unread.mark_as_read(35);
    assert.equal(unread.num_unread_for_topic(1, 'test'), 2);

    unread.mark_as_read(34);
    assert.equal(unread.num_unread_for_person('4,6,101'), 1);
}());

(function test_errors() {
    unread.declare_bankruptcy();

    global.blueslip.warn = function () {};

    // Test unknown message leads to zero count
    var message = {
        id: 9,
        type: 'private',
        display_recipient: [{id: 9999}],
    };

    unread.mark_as_read(message.id);
    var counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);
}());

