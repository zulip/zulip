var assert = require('assert');

add_dependencies({
    _: 'third/underscore/underscore.js',
    util: 'js/util.js',
    Dict: 'js/dict.js',
    stream_data: 'js/stream_data.js',
    Filter: 'js/filter.js'
});

var narrow = require('js/narrow.js');
var Filter = global.Filter;
var stream_data = global.stream_data;

(function test_parse_and_unparse() {
    var string ='stream:Foo topic:Bar yo';
    var operators = [['stream', 'Foo'], ['topic', 'Bar'], ['search', 'yo']];

    assert.deepEqual(narrow.parse(string), operators);

    string = 'stream:Foo topic:Bar yo';
    assert.deepEqual(narrow.unparse(operators), string);
}());

(function test_stream() {
    var operators = [['stream', 'Foo'], ['topic', 'Bar'], ['search', 'yo']];
    narrow._set_current_filter(new Filter(operators));

    assert.equal(narrow.stream(), 'Foo');
}());

(function test_operators() {
    var operators = [['stream', 'Foo'], ['topic', 'Bar'], ['search', 'Yo']];
    var canonical_operators = [['stream', 'Foo'], ['topic', 'Bar'], ['search', 'yo']];
    narrow._set_current_filter(new Filter(operators));

    assert.deepEqual(narrow.operators(), canonical_operators);
}());

(function test_set_compose_defaults() {
    var operators = [['stream', 'Foo'], ['topic', 'Bar']];
    narrow._set_current_filter(new Filter(operators));

    var opts = {};
    narrow.set_compose_defaults(opts);
    assert.equal(opts.stream, 'Foo');
    assert.equal(opts.subject, 'Bar');

    stream_data.add_sub('ROME', {name: 'ROME'});
    operators = [['stream', 'rome']];
    narrow._set_current_filter(new Filter(operators));

    opts = {};
    narrow.set_compose_defaults(opts);
    assert.equal(opts.stream, 'ROME');
}());
