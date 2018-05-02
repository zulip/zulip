zrequire('Filter', 'js/filter');
zrequire('people');
zrequire('stream_data');
zrequire('unread');
zrequire('util');
set_global('blueslip', global.make_zblueslip());

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

(function test_get_unread_ids() {
    var unread_ids;
    var terms;
    var msg;

    const sub = {
        name: 'My Stream',
        stream_id: 55,
    };
    stream_data.add_sub(sub.name, sub);

    unread_ids = narrow_state.get_unread_ids();
    assert.equal(unread_ids, undefined);

    terms = [
        {operator: 'sender', operand: 'me@example.com'},
    ];
    set_filter(terms);
    unread_ids = narrow_state.get_unread_ids();
    assert.equal(unread_ids, undefined);

    terms = [
        {operator: 'stream', operand: 'bogus'},
    ];
    set_filter(terms);
    unread_ids = narrow_state.get_unread_ids();
    assert.deepEqual(unread_ids, []);

    terms = [
        {operator: 'stream', operand: sub.name},
    ];
    set_filter(terms);
    unread_ids = narrow_state.get_unread_ids();
    assert.deepEqual(unread_ids, []);

    msg = {
        id: 101,
        type: 'stream',
        stream_id: sub.stream_id,
        subject: 'my topic',
        unread: true,
        mentioned: true,
    };
    unread.process_loaded_messages([msg]);

    unread_ids = narrow_state.get_unread_ids();
    assert.deepEqual(unread_ids, [msg.id]);

    terms = [
        {operator: 'stream', operand: 'bogus'},
        {operator: 'topic', operand: 'my topic'},
    ];
    set_filter(terms);
    unread_ids = narrow_state.get_unread_ids();
    assert.deepEqual(unread_ids, []);

    terms = [
        {operator: 'stream', operand: sub.name},
        {operator: 'topic', operand: 'my topic'},
    ];
    set_filter(terms);
    unread_ids = narrow_state.get_unread_ids();
    assert.deepEqual(unread_ids, [msg.id]);

    terms = [
        {operator: 'is', operand: 'mentioned'},
    ];
    set_filter(terms);
    unread_ids = narrow_state.get_unread_ids();
    assert.deepEqual(unread_ids, [msg.id]);

    terms = [
        {operator: 'pm-with', operand: 'alice@example.com'},
    ];
    set_filter(terms);
    unread_ids = narrow_state.get_unread_ids();
    assert.deepEqual(unread_ids, []);

    msg = {
        id: 102,
        type: 'private',
        unread: true,
        display_recipient: [
            {user_id: alice.user_id},
        ],
    };
    unread.process_loaded_messages([msg]);

    unread_ids = narrow_state.get_unread_ids();
    assert.deepEqual(unread_ids, [msg.id]);

    terms = [
        {operator: 'is', operand: 'private'},
    ];
    set_filter(terms);
    unread_ids = narrow_state.get_unread_ids();
    assert.deepEqual(unread_ids, [msg.id]);

    terms = [
        {operator: 'pm-with', operand: 'bob@example.com'},
    ];
    set_filter(terms);

    blueslip.set_test_data('warn', 'Unknown emails: bob@example.com');
    unread_ids = narrow_state.get_unread_ids();
    assert.deepEqual(unread_ids, []);
}());
