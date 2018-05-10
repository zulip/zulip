zrequire('Filter', 'js/filter');
zrequire('people');
zrequire('stream_data');
zrequire('unread');
zrequire('util');
set_global('blueslip', global.make_zblueslip());

set_global('message_store', {});
set_global('page_params', {});

set_global('muting', {
    is_topic_muted: () => false,
});

// The main code we are testing lives here.
zrequire('narrow_state');

const alice = {
    email: 'alice@example.com',
    user_id: 11,
    full_name: 'Alice',
};

people.init();
people.add(alice);
people.is_my_user_id = () => false;

function set_filter(terms) {
    const filter = new Filter(terms);
    narrow_state.set_current_filter(filter);
}

function assert_unread_info(expected) {
    assert.deepEqual(narrow_state.get_first_unread_info(), expected);
}

function candidate_ids() {
    return narrow_state._possible_unread_message_ids();
}

(function test_get_unread_ids() {
    var unread_ids;
    var terms;

    const sub = {
        name: 'My Stream',
        stream_id: 55,
    };

    const stream_msg = {
        id: 101,
        type: 'stream',
        stream_id: sub.stream_id,
        subject: 'my topic',
        unread: true,
        mentioned: true,
    };

    const private_msg = {
        id: 102,
        type: 'private',
        unread: true,
        display_recipient: [
            {user_id: alice.user_id},
        ],
    };

    stream_data.add_sub(sub.name, sub);

    unread_ids = candidate_ids();
    assert.equal(unread_ids, undefined);

    terms = [
        {operator: 'bogus_operator', operand: 'me@example.com'},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.equal(unread_ids, undefined);
    assert_unread_info({flavor: 'cannot_compute'});

    terms = [
        {operator: 'stream', operand: 'bogus'},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    terms = [
        {operator: 'stream', operand: sub.name},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);
    assert_unread_info({flavor: 'not_found'});

    unread.process_loaded_messages([stream_msg]);
    message_store.get = (msg_id) => {
        assert.equal(msg_id, stream_msg.id);
        return stream_msg;
    };

    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id]);
    assert_unread_info({
        flavor: 'found',
        msg_id: stream_msg.id,
    });

    terms = [
        {operator: 'stream', operand: 'bogus'},
        {operator: 'topic', operand: 'my topic'},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    terms = [
        {operator: 'stream', operand: sub.name},
        {operator: 'topic', operand: 'my topic'},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id]);

    terms = [
        {operator: 'is', operand: 'mentioned'},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id]);

    terms = [
        {operator: 'sender', operand: 'me@example.com'},
    ];
    set_filter(terms);
    // note that our candidate ids are just "all" ids now
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [stream_msg.id]);

    // this actually does filtering
    assert_unread_info({flavor: 'not_found'});

    terms = [
        {operator: 'pm-with', operand: 'alice@example.com'},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    unread.process_loaded_messages([private_msg]);

    message_store.get = (msg_id) => {
        assert.equal(msg_id, private_msg.id);
        return private_msg;
    };

    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [private_msg.id]);

    assert_unread_info({
        flavor: 'found',
        msg_id: private_msg.id,
    });

    terms = [
        {operator: 'is', operand: 'private'},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, [private_msg.id]);

    terms = [
        {operator: 'pm-with', operand: 'bob@example.com'},
    ];
    set_filter(terms);

    blueslip.set_test_data('warn', 'Unknown emails: bob@example.com');
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    terms = [
        {operator: 'is', operand: 'starred'},
    ];
    set_filter(terms);
    unread_ids = candidate_ids();
    assert.deepEqual(unread_ids, []);

    terms = [
        {operator: 'search', operand: 'needle'},
    ];
    set_filter(terms);

    blueslip.set_test_data('error', 'unexpected call to get_first_unread_info');
    assert_unread_info({
        flavor: 'cannot_compute',
    });
}());
