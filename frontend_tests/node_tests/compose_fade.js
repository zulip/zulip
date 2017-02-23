set_global('$', function () {
});

add_dependencies({
    people: 'js/people',
    stream_data: 'js/stream_data',
    util: 'js/util',
});

var compose_fade = require('js/compose_fade.js');

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

people.add(me);
people.initialize_current_user(me.user_id);

people.add(alice);
people.add(bob);


(function test_set_focused_recipient() {
    var sub = {
        stream_id: 101,
        name: 'social',
        subscribed: true,
    };
    stream_data.add_sub('social', sub);
    stream_data.set_subscribers(sub, [me.user_id, alice.user_id]);

    global.$ = function (selector) {
        switch (selector) {
        case '#stream':
            return {
                val: function () {
                    return 'social';
                },
            };
        case '#subject':
            return {
                val: function () {
                    return 'lunch';
                },
            };
        }
    };

    compose_fade.set_focused_recipient('stream');

    assert(compose_fade.would_receive_message('me@example.com'));
    assert(compose_fade.would_receive_message('alice@example.com'));
    assert(!compose_fade.would_receive_message('bob@example.com'));

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
}());
