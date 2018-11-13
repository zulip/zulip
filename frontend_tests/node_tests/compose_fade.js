set_global('blueslip', {});
global.blueslip.warn = function () {};

zrequire('util');
zrequire('stream_data');
zrequire('people');
zrequire('compose_fade');

var me = {
    email: 'me@example.com',
    user_id: 30,
    full_name: 'Me Myself',
};

var alice = {
    email: 'alice@example.com',
    user_id: 31,
    full_name: 'Alice',
};

var bob = {
    email: 'bob@example.com',
    user_id: 32,
    full_name: 'Bob',
};

people.add_in_realm(me);
people.initialize_current_user(me.user_id);

people.add_in_realm(alice);
people.add_in_realm(bob);


run_test('set_focused_recipient', () => {
    var sub = {
        stream_id: 101,
        name: 'social',
        subscribed: true,
        can_access_subscribers: true,
    };
    stream_data.add_sub('social', sub);
    stream_data.set_subscribers(sub, [me.user_id, alice.user_id]);

    global.$ = function (selector) {
        switch (selector) {
        case '#stream_message_recipient_stream':
            return {
                val: function () {
                    return 'social';
                },
            };
        case '#stream_message_recipient_topic':
            return {
                val: function () {
                    return 'lunch';
                },
            };
        }
    };

    compose_fade.set_focused_recipient('stream');

    assert.equal(compose_fade.would_receive_message('me@example.com'), true);
    assert.equal(compose_fade.would_receive_message('alice@example.com'), true);
    assert.equal(compose_fade.would_receive_message('bob@example.com'), false);
    assert.equal(compose_fade.would_receive_message('nonrealmuser@example.com'), true);

    var good_msg = {
        type: 'stream',
        stream_id: 101,
        subject: 'lunch',
    };
    var bad_msg = {
        type: 'stream',
        stream_id: 999,
        subject: 'lunch',
    };
    assert(!compose_fade.should_fade_message(good_msg));
    assert(compose_fade.should_fade_message(bad_msg));
});
