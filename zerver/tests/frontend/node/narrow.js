add_dependencies({
    stream_data: 'js/stream_data.js',
    Filter: 'js/filter.js'
});

var narrow = require('js/narrow.js');
var Filter = global.Filter;
var stream_data = global.stream_data;
var _ = global._;

function set_filter(operators) {
    operators = _.map(operators, function (op) {
        return {operator: op[0], operand: op[1]};
    });
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
    var result = narrow.operators();
    assert.equal(result.length, 3);
    assert.equal(result[0].operator, 'stream');
    assert.equal(result[0].operand, 'Foo');

    assert.equal(result[1].operator, 'topic');
    assert.equal(result[1].operand, 'Bar');

    assert.equal(result[2].operator, 'search');
    assert.equal(result[2].operand, 'yo');
}());

(function test_muting_enabled() {
    set_filter([['stream', 'devel']]);
    assert(narrow.muting_enabled());

    narrow._set_current_filter(undefined); // not narrowed, basically
    assert(narrow.muting_enabled());

    set_filter([['stream', 'devel'], ['topic', 'mac']]);
    assert(!narrow.muting_enabled());

    set_filter([['search', 'whatever']]);
    assert(!narrow.muting_enabled());

    set_filter([['is', 'private']]);
    assert(!narrow.muting_enabled());

}());

(function test_set_compose_defaults() {
    set_filter([['stream', 'Foo'], ['topic', 'Bar']]);

    var opts = {};
    narrow.set_compose_defaults(opts);
    assert.equal(opts.stream, 'Foo');
    assert.equal(opts.subject, 'Bar');

    stream_data.add_sub('ROME', {name: 'ROME', stream_id: 99});
    set_filter([['stream', 'rome']]);

    opts = {};
    narrow.set_compose_defaults(opts);
    assert.equal(opts.stream, 'ROME');
}());
