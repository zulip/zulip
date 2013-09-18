var assert = require('assert');

add_dependencies({
    _: 'third/underscore/underscore.js',
    Dict: 'js/dict.js',
    stream_data: 'js/stream_data.js',
    Filter: 'js/filter.js'
});

var narrow = require('js/narrow.js');
var Filter = global.Filter;
var stream_data = global.stream_data;

function set_filter(operators) {
    narrow._set_current_filter(new Filter(operators));
}

(function test_stream() {
    set_filter([['stream', 'Foo'], ['topic', 'Bar'], ['search', 'yo']]);

    assert.equal(narrow.stream(), 'Foo');
}());


(function test_narrowed() {
    narrow._set_current_filter(undefined); // not narrowed, basically
    assert(!narrow.narrowed_to_pms());
    assert(!narrow.narrowed_by_reply());
    assert(!narrow.narrowed_to_search());
    assert(!narrow.narrowed_to_topic());

    set_filter([['stream', 'Foo']]);
    assert(!narrow.narrowed_to_pms());
    assert(!narrow.narrowed_by_reply());
    assert(!narrow.narrowed_to_search());
    assert(!narrow.narrowed_to_topic());

    set_filter([['pm-with', 'steve@zulip.com']]);
    assert(narrow.narrowed_to_pms());
    assert(narrow.narrowed_by_reply());
    assert(!narrow.narrowed_to_search());
    assert(!narrow.narrowed_to_topic());

    set_filter([['stream', 'Foo'], ['topic', 'bar']]);
    assert(!narrow.narrowed_to_pms());
    assert(narrow.narrowed_by_reply());
    assert(!narrow.narrowed_to_search());
    assert(narrow.narrowed_to_topic());

    set_filter([['search', 'grail']]);
    assert(!narrow.narrowed_to_pms());
    assert(!narrow.narrowed_by_reply());
    assert(narrow.narrowed_to_search());
    assert(!narrow.narrowed_to_topic());
}());

(function test_operators() {
    set_filter([['stream', 'Foo'], ['topic', 'Bar'], ['search', 'Yo']]);
    var canonical_operators = [['stream', 'Foo'], ['topic', 'Bar'], ['search', 'yo']];

    assert.deepEqual(narrow.operators(), canonical_operators);
}());

(function test_set_compose_defaults() {
    set_filter([['stream', 'Foo'], ['topic', 'Bar']]);

    var opts = {};
    narrow.set_compose_defaults(opts);
    assert.equal(opts.stream, 'Foo');
    assert.equal(opts.subject, 'Bar');

    stream_data.add_sub('ROME', {name: 'ROME'});
    set_filter([['stream', 'rome']]);

    opts = {};
    narrow.set_compose_defaults(opts);
    assert.equal(opts.stream, 'ROME');
}());
