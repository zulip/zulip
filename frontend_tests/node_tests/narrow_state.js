add_dependencies({
    people: 'js/people.js',
    stream_data: 'js/stream_data.js',
    Filter: 'js/filter.js',
});

set_global('page_params', {
});

var narrow_state = require('js/narrow_state.js');

var Filter = global.Filter;
var stream_data = global.stream_data;
var _ = global._;

function set_filter(operators) {
    operators = _.map(operators, function (op) {
        return {operator: op[0], operand: op[1]};
    });
    narrow_state.set_current_filter(new Filter(operators));
}


(function test_stream() {
    assert.equal(narrow_state.public_operators(), undefined);
    assert(!narrow_state.active());

    var test_stream = {name: 'Test', stream_id: 15};
    stream_data.add_sub('Test', test_stream);

    assert(!narrow_state.is_for_stream_id(test_stream.stream_id));

    set_filter([
        ['stream', 'Test'],
        ['topic', 'Bar'],
        ['search', 'yo'],
    ]);
    assert(narrow_state.active());

    assert.equal(narrow_state.stream(), 'Test');
    assert.equal(narrow_state.topic(), 'Bar');
    assert(narrow_state.is_for_stream_id(test_stream.stream_id));

    var expected_operators = [
        { negated: false, operator: 'stream', operand: 'Test' },
        { negated: false, operator: 'topic', operand: 'Bar' },
        { negated: false, operator: 'search', operand: 'yo' },
    ];

    var public_operators = narrow_state.public_operators();
    assert.deepEqual(public_operators, expected_operators);
    assert.equal(narrow_state.search_string(), 'stream:Test topic:Bar yo');
}());


(function test_narrowed() {
    narrow_state.reset_current_filter(); // not narrowed, basically
    assert(!narrow_state.narrowed_to_pms());
    assert(!narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());

    set_filter([['stream', 'Foo']]);
    assert(!narrow_state.narrowed_to_pms());
    assert(!narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());

    set_filter([['pm-with', 'steve@zulip.com']]);
    assert(narrow_state.narrowed_to_pms());
    assert(narrow_state.narrowed_by_reply());
    assert(narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());

    set_filter([['stream', 'Foo'], ['topic', 'bar']]);
    assert(!narrow_state.narrowed_to_pms());
    assert(narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(narrow_state.narrowed_to_topic());

    set_filter([['search', 'grail']]);
    assert(!narrow_state.narrowed_to_pms());
    assert(!narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());
}());

(function test_operators() {
    set_filter([['stream', 'Foo'], ['topic', 'Bar'], ['search', 'Yo']]);
    var result = narrow_state.operators();
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
    assert(narrow_state.muting_enabled());

    narrow_state.reset_current_filter(); // not narrowed, basically
    assert(narrow_state.muting_enabled());

    set_filter([['stream', 'devel'], ['topic', 'mac']]);
    assert(!narrow_state.muting_enabled());

    set_filter([['search', 'whatever']]);
    assert(!narrow_state.muting_enabled());

    set_filter([['is', 'private']]);
    assert(!narrow_state.muting_enabled());

}());

(function test_set_compose_defaults() {
    set_filter([['stream', 'Foo'], ['topic', 'Bar']]);

    var opts = {};
    narrow_state.set_compose_defaults(opts);
    assert.equal(opts.stream, 'Foo');
    assert.equal(opts.subject, 'Bar');

    stream_data.add_sub('ROME', {name: 'ROME', stream_id: 99});
    set_filter([['stream', 'rome']]);

    opts = {};
    narrow_state.set_compose_defaults(opts);
    assert.equal(opts.stream, 'ROME');
}());

(function test_update_email() {
    var steve = {
        email: 'steve@foo.com',
        user_id: 43,
        full_name: 'Steve',
    };

    people.add(steve);
    set_filter([
        ['pm-with', 'steve@foo.com'],
        ['sender', 'steve@foo.com'],
        ['stream', 'steve@foo.com'], // try to be tricky
    ]);
    narrow_state.update_email(steve.user_id, 'showell@foo.com');
    var filter = narrow_state.filter();
    assert.deepEqual(filter.operands('pm-with'), ['showell@foo.com']);
    assert.deepEqual(filter.operands('sender'), ['showell@foo.com']);
    assert.deepEqual(filter.operands('stream'), ['steve@foo.com']);
}());
