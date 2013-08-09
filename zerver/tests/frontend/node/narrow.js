var assert = require('assert');

(function set_up_dependencies () {
    global._ = require('third/underscore/underscore.js');
    global.util = require('js/util.js');
    global.narrow = require('js/narrow.js');
    global.$ = function () {}; // for subs.js
    global.subs = require('js/subs.js');
}());

var narrow = global.narrow;

(function test_parse_and_unparse() {
    var string ='stream:Foo topic:Bar yo';
    var operators = [['stream', 'Foo'], ['topic', 'Bar'], ['search', 'yo']];

    assert.deepEqual(narrow.parse(string), operators);

    string = 'stream:foo topic:bar yo';
    assert.deepEqual(narrow.unparse(operators), string);
}());

(function test_stream() {
    var operators = [['stream', 'Foo'], ['topic', 'Bar'], ['search', 'yo']];
    narrow._set_current_filter(new narrow.Filter(operators));

    assert.equal(narrow.stream(), 'foo');
}());

(function test_operators() {
    var operators = [['stream', 'Foo'], ['topic', 'Bar'], ['search', 'yo']];
    var canonical_operators = [['stream', 'foo'], ['topic', 'bar'], ['search', 'yo']];
    narrow._set_current_filter(new narrow.Filter(operators));

    assert.deepEqual(narrow.operators(), canonical_operators);
}());
