zrequire('people');
zrequire('Filter', 'js/filter');
zrequire('stream_data');
zrequire('narrow_state');

set_global('blueslip', {});
set_global('page_params', {
});

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

    var bad_stream_id = 1000000;
    var called = false;
    global.blueslip.error = function (msg) {
        assert.equal(msg, 'Bad stream id ' + bad_stream_id);
        called = true;
    };
    assert(!narrow_state.is_for_stream_id(bad_stream_id));
    assert(called);

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
    assert(!narrow_state.narrowed_by_stream_reply());

    set_filter([['stream', 'Foo']]);
    assert(!narrow_state.narrowed_to_pms());
    assert(!narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());
    assert(narrow_state.narrowed_by_stream_reply());

    set_filter([['pm-with', 'steve@zulip.com']]);
    assert(narrow_state.narrowed_to_pms());
    assert(narrow_state.narrowed_by_reply());
    assert(narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());
    assert(!narrow_state.narrowed_by_stream_reply());

    set_filter([['stream', 'Foo'], ['topic', 'bar']]);
    assert(!narrow_state.narrowed_to_pms());
    assert(narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(narrow_state.narrowed_to_topic());
    assert(!narrow_state.narrowed_by_stream_reply());

    set_filter([['search', 'grail']]);
    assert(!narrow_state.narrowed_to_pms());
    assert(!narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());
    assert(!narrow_state.narrowed_by_stream_reply());
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

    narrow_state.reset_current_filter();
    result = narrow_state.operators();
    assert.equal(result.length, 0);
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

    var stream_and_subject = narrow_state.set_compose_defaults();
    assert.equal(stream_and_subject.stream, 'Foo');
    assert.equal(stream_and_subject.subject, 'Bar');

    set_filter([['pm-with', 'foo@bar.com']]);
    var pm_test = narrow_state.set_compose_defaults();
    assert.equal(pm_test.private_message_recipient, 'foo@bar.com');

    set_filter([['topic', 'duplicate'], ['topic', 'duplicate']]);
    assert.deepEqual(narrow_state.set_compose_defaults(), {});

    stream_data.add_sub('ROME', {name: 'ROME', stream_id: 99});
    set_filter([['stream', 'rome']]);

    var stream_test = narrow_state.set_compose_defaults();
    assert.equal(stream_test.stream, 'ROME');
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

(function test_topic() {
    set_filter([['stream', 'Foo'], ['topic', 'Bar']]);
    assert.equal(narrow_state.topic(), 'Bar');

    set_filter([['stream', 'release'], ['topic', '@#$$^test']]);
    assert.equal(narrow_state.topic(), '@#$$^test');

    set_filter(undefined);
    assert.equal(narrow_state.topic(), undefined);

    set_filter([
        ['sender', 'test@foo.com'],
        ['pm-with', 'test@foo.com'],
    ]);
    assert.equal(narrow_state.topic(), undefined);

    narrow_state.set_current_filter(undefined);
    assert.equal(narrow_state.topic(), undefined);
}());


(function test_stream() {
    set_filter(undefined);
    assert.equal(narrow_state.stream(), undefined);

    set_filter([['stream', 'Foo'], ['topic', 'Bar']]);
    assert.equal(narrow_state.stream(), 'Foo');

    set_filter([['sender', 'someone'], ['topic', 'random']]);
    assert.equal(narrow_state.stream(), undefined);
}());

(function test_pm_string() {
    // This function will return undefined unless we're clearly
    // narrowed to a specific PM (including huddles) with real
    // users.
    narrow_state.set_current_filter(undefined);
    assert.equal(narrow_state.pm_string(), undefined);

    set_filter([['stream', 'Foo'], ['topic', 'Bar']]);
    assert.equal(narrow_state.pm_string(), undefined);

    set_filter([['pm-with', '']]);
    assert.equal(narrow_state.pm_string(), undefined);

    var called = false;
    blueslip.warn = function (error) {
        assert.equal(error, 'Unknown emails: bogus@foo.com');
        called = true;
    };

    set_filter([['pm-with', 'bogus@foo.com']]);
    assert.equal(narrow_state.pm_string(), undefined);
    assert(called);

    var alice = {
        email: 'alice@foo.com',
        user_id: 444,
        full_name: 'Alice',
    };

    var bob = {
        email: 'bob@foo.com',
        user_id: 555,
        full_name: 'Bob',
    };

    people.add(alice);
    people.add(bob);

    set_filter([['pm-with', 'bob@foo.com,alice@foo.com']]);
    assert.equal(narrow_state.pm_string(), '444,555');
}());
