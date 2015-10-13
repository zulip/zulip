add_dependencies({
    stream_color: 'js/stream_color.js'
});

set_global('blueslip', {});

var stream_data = require('js/stream_data.js');

(function test_basics() {
    var denmark = {
        subscribed: false,
        color: 'blue',
        name: 'Denmark',
        stream_id: 1,
        in_home_view: false
    };
    var social = {
        subscribed: true,
        color: 'red',
        name: 'social',
        stream_id: 2,
        in_home_view: true,
        invite_only: true
    };
    var test = {
        subscribed: true,
        color: 'yellow',
        name: 'test',
        stream_id: 3,
        in_home_view: false,
        invite_only: false
    };
    stream_data.add_sub('Denmark', denmark);
    stream_data.add_sub('social', social);
    assert(stream_data.all_subscribed_streams_are_in_home_view());
    stream_data.add_sub('test', test);
    assert(!stream_data.all_subscribed_streams_are_in_home_view());

    assert.equal(stream_data.get_sub('denmark'), denmark);
    assert.equal(stream_data.get_sub('Social'), social);

    assert.deepEqual(stream_data.home_view_stream_names(), ['social']);
    assert.deepEqual(stream_data.subscribed_streams(), ['social', 'test']);
    assert.deepEqual(stream_data.get_colors(), ['red', 'yellow']);

    assert(stream_data.is_subscribed('social'));
    assert(stream_data.is_subscribed('Social'));
    assert(!stream_data.is_subscribed('Denmark'));
    assert(!stream_data.is_subscribed('Rome'));

    assert(stream_data.get_invite_only('social'));
    assert(!stream_data.get_invite_only('unknown'));
    assert.equal(stream_data.get_color('social'), 'red');
    assert.equal(stream_data.get_color('unknown'), global.stream_color.default_color);

    assert.equal(stream_data.get_name('denMARK'), 'Denmark');
    assert.equal(stream_data.get_name('unknown Stream'), 'unknown Stream');

    assert(stream_data.in_home_view('social'));
    assert(!stream_data.in_home_view('denmark'));

    // Deleting a subscription makes you unsubscribed from the perspective of
    // the client.
    // Deleting a subscription is case-insensitive.
    stream_data.delete_sub('SOCIAL');
    assert(!stream_data.is_subscribed('social'));
}());

(function test_get_by_id() {
    stream_data.clear_subscriptions();
    var id = 42;
    var sub = {
        name: 'Denmark',
        subscribed: true,
        color: 'red',
        stream_id: id
    };
    stream_data.add_sub('Denmark', sub);
    sub = stream_data.get_sub('Denmark');
    assert.equal(sub.color, 'red');
    sub = stream_data.get_sub_by_id(id);
    assert.equal(sub.color, 'red');
}());

(function test_subscribers() {
    stream_data.clear_subscriptions();
    var sub = {name: 'Rome', subscribed: true, stream_id: 1};

    stream_data.add_sub('Rome', sub);

    stream_data.set_subscribers(sub, ['fred@zulip.com', 'george@zulip.com']);
    assert(stream_data.user_is_subscribed('Rome', 'FRED@zulip.com'));
    assert(stream_data.user_is_subscribed('Rome', 'fred@zulip.com'));
    assert(stream_data.user_is_subscribed('Rome', 'george@zulip.com'));
    assert(!stream_data.user_is_subscribed('Rome', 'not_fred@zulip.com'));

    stream_data.set_subscribers(sub, []);

    var email = 'brutus@zulip.com';
    assert(!stream_data.user_is_subscribed('Rome', email));

    // add
    stream_data.add_subscriber('Rome', email);
    assert(stream_data.user_is_subscribed('Rome', email));

    // verify that adding an already-removed subscriber is a noop
    stream_data.add_subscriber('Rome', email);
    assert(stream_data.user_is_subscribed('Rome', email));

    // remove
    stream_data.remove_subscriber('Rome', email);
    assert(!stream_data.user_is_subscribed('Rome', email));

    // verify that removing an already-removed subscriber is a noop
    stream_data.remove_subscriber('Rome', email);
    assert(!stream_data.user_is_subscribed('Rome', email));

    // Verify defensive code in set_subscribers, where the second parameter
    // can be undefined.
    stream_data.set_subscribers(sub);
    stream_data.add_sub('Rome', sub);
    stream_data.add_subscriber('Rome', email);
    sub.subscribed = true;
    assert(stream_data.user_is_subscribed('Rome', email));

    // Verify that we noop and don't crash when unsubsribed.
    sub.subscribed = false;
    global.blueslip.warn = function () {};
    stream_data.add_subscriber('Rome', email);
    assert.equal(stream_data.user_is_subscribed('Rome', email), undefined);
    stream_data.remove_subscriber('Rome', email);
    assert.equal(stream_data.user_is_subscribed('Rome', email), undefined);

}());
