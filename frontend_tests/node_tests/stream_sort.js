var assert = require('assert');

add_dependencies({
    stream_data: 'js/stream_data.js',
    util: 'js/util.js',
});

var stream_sort = require('js/stream_sort.js');
var stream_data = require('js/stream_data.js');
var with_overrides = global.with_overrides;

// Test no subscribed streams
(function test_no_subscribed_streams() {
    assert.equal(stream_sort.sort_groups(''), undefined);
}());

stream_data.add_sub('scalene', {
    subscribed: true,
    name: 'scalene',
    stream_id: 1,
    pin_to_top: true,
});
stream_data.add_sub('fast tortoise', {
    subscribed: true,
    name: 'fast tortoise',
    stream_id: 2,
    pin_to_top: false,
});
stream_data.add_sub('pneumonia', {
    subscribed: true,
    name: 'pneumonia',
    stream_id: 3,
    pin_to_top: false,
});
stream_data.add_sub('clarinet', {
    subscribed: true,
    name: 'clarinet',
    stream_id: 4,
    pin_to_top: false,
});
stream_data.add_sub('weaving', {
    subscribed: false,
    name: 'weaving',
    stream_id: 5,
    pin_to_top: false,
});

with_overrides(function (override) {
    override('stream_data.is_active', function (sub) {
        return (sub.name !== "pneumonia");
    });

    // Test sorting into categories/alphabetized
    var sorted = stream_sort.sort_groups("");
    assert.deepEqual(sorted.pinned_streams, ['scalene']);
    assert.deepEqual(sorted.normal_streams, ['clarinet', 'fast tortoise']);
    assert.deepEqual(sorted.dormant_streams, ['pneumonia']);

    // Test filtering
    sorted = stream_sort.sort_groups("s");
    assert.deepEqual(sorted.pinned_streams, ['scalene']);
    assert.deepEqual(sorted.normal_streams, []);
    assert.deepEqual(sorted.dormant_streams, []);

    // Test searching entire word, case-insensitive
    sorted = stream_sort.sort_groups("PnEuMoNiA");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, []);
    assert.deepEqual(sorted.dormant_streams, ['pneumonia']);

    // Test searching part of word
    sorted = stream_sort.sort_groups("tortoise");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, ['fast tortoise']);
    assert.deepEqual(sorted.dormant_streams, []);

    // Test searching stream with spaces
    sorted = stream_sort.sort_groups("fast t");
    assert.deepEqual(sorted.pinned_streams, []);
    assert.deepEqual(sorted.normal_streams, ['fast tortoise']);
    assert.deepEqual(sorted.dormant_streams, []);
});
