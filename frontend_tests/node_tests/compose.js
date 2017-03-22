set_global('$', function () {
});

set_global('page_params', {
    use_websockets: false,
});

set_global('document', {
    location: {
    },
});

add_dependencies({
    people: 'js/people',
    stream_data: 'js/stream_data',
    util: 'js/util',
});

var compose = require('js/compose.js');

set_global('compose_state', {
    recipient: compose.recipient,
});

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

    var page = {
        '#stream': 'social',
        '#subject': 'lunch',
        '#new_message_content': 'burrito',
        '#private_message_recipient': 'alice@example.com,    bob@example.com',
    };

    global.$ = function (selector) {
        return {
            val: function () {
                return page[selector];
            },
        };
    };

    global.compose_state.composing = function () {
        return 'stream';
    };

    global.$.trim = function (s) {
        return s;
    };


    var message = compose.snapshot_message();
    assert.equal(message.to, 'social');
    assert.equal(message.subject, 'lunch');
    assert.equal(message.content, 'burrito');

    global.compose_state.composing = function () {
        return 'private';
    };
    message = compose.snapshot_message();
    assert.deepEqual(message.to, ['alice@example.com', 'bob@example.com']);
    assert.equal(message.to_user_ids, '31,32');
    assert.equal(message.content, 'burrito');

}());

(function test_get_focus_area() {
    assert.equal(compose._get_focus_area('private', {}), 'private_message_recipient');
    assert.equal(compose._get_focus_area('private', {
        private_message_recipient: 'bob@example.com'}), 'new_message_content');
    assert.equal(compose._get_focus_area('stream', {}), 'stream');
    assert.equal(compose._get_focus_area('stream', {stream: 'fun'}),
                 'subject');
    assert.equal(compose._get_focus_area('stream', {stream: 'fun',
                                                    subject: 'more'}),
                 'new_message_content');
    assert.equal(compose._get_focus_area('stream', {stream: 'fun',
                                                    subject: 'more',
                                                    trigger: 'new topic button'}),
                 'subject');
}());
