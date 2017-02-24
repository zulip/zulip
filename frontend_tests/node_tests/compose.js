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
    stream_data: 'js/stream_data',
    util: 'js/util',
});

var compose = require('js/compose.js');

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

    compose.composing = function () {
        return 'stream';
    };

    global.$.trim = function (s) {
        return s;
    };


    var message = compose.snapshot_message();
    assert.equal(message.to, 'social');
    assert.equal(message.subject, 'lunch');
    assert.equal(message.content, 'burrito');

    compose.composing = function () {
        return 'private';
    };
    message = compose.snapshot_message();
    assert.deepEqual(message.to, ['alice@example.com', 'bob@example.com']);
    assert.equal(message.content, 'burrito');

}());
