var assert = require('assert');

add_dependencies({
    _: 'third/underscore/underscore.js',
    util: 'js/util.js',
    Dict: 'js/dict.js',
    stream_color: 'js/stream_color.js'
});

var stream_data = require('js/stream_data.js');

(function test_basics() {
    var denmark = {
        subscribed: false,
        color: 'blue',
        name: 'Denmark',
        in_home_view: false
    };
    var social = {
        subscribed: true,
        color: 'red',
        name: 'social',
        in_home_view: true,
        invite_only: true
    };
    stream_data.add_sub('Denmark', denmark);
    stream_data.add_sub('social', social);

    assert.equal(stream_data.get_sub('denmark'), denmark);
    assert.equal(stream_data.get_sub('Social'), social);

    assert.deepEqual(stream_data.subscribed_streams(), ['social']);
    assert.deepEqual(stream_data.get_colors(), ['red']);

    assert(stream_data.all_subscribed_streams_are_in_home_view());

    assert(stream_data.is_subscribed('social'));
    assert(stream_data.is_subscribed('Social'));
    assert(!stream_data.is_subscribed('Denmark'));
    assert(!stream_data.is_subscribed('Rome'));

    assert(stream_data.get_invite_only('social'));
    assert.equal(stream_data.get_color('social'), 'red');
    assert.equal(stream_data.get_color('unknown'), global.stream_color.default_color);

    assert.equal(stream_data.get_name('denMARK'), 'Denmark');
    assert.equal(stream_data.get_name('unknown Stream'), 'unknown Stream');
}());

(function test_get_and_set() {
    stream_data.clear_subscriptions();
    stream_data.add_sub('Denmark', {name: 'Denmark', subscribed: true});
    assert.deepEqual(stream_data.subscribed_streams(), ['Denmark']);
    var info = stream_data.get_stream_info();
    stream_data.clear_subscriptions();
    assert.deepEqual(stream_data.subscribed_streams(), []);
    stream_data.set_stream_info(info);
    assert.deepEqual(stream_data.subscribed_streams(), ['Denmark']);
}());
