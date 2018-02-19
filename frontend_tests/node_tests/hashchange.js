zrequire('people');
zrequire('hash_util');
zrequire('hashchange');
zrequire('stream_data');

(function test_operators_round_trip() {
    var operators;
    var hash;
    var narrow;

    operators = [
        {operator: 'stream', operand: 'devel'},
        {operator: 'topic', operand: 'algol'},
    ];
    hash = hashchange.operators_to_hash(operators);
    assert.equal(hash, '#narrow/stream/devel/topic/algol');

    narrow = hashchange.parse_narrow(hash.split('/'));
    assert.deepEqual(narrow, [
        {operator: 'stream', operand: 'devel', negated: false},
        {operator: 'topic', operand: 'algol', negated: false},
    ]);

    operators = [
        {operator: 'stream', operand: 'devel'},
        {operator: 'topic', operand: 'visual c++', negated: true},
    ];
    hash = hashchange.operators_to_hash(operators);
    assert.equal(hash, '#narrow/stream/devel/-topic/visual.20c.2B.2B');

    narrow = hashchange.parse_narrow(hash.split('/'));
    assert.deepEqual(narrow, [
        {operator: 'stream', operand: 'devel', negated: false},
        {operator: 'topic', operand: 'visual c++', negated: true},
    ]);

    // test new encodings, where we have a stream id
    var florida_stream = {
        name: 'Florida, USA',
        stream_id: 987,
    };
    stream_data.add_sub(florida_stream.name, florida_stream);
    operators = [
        {operator: 'stream', operand: 'Florida, USA'},
    ];
    hash = hashchange.operators_to_hash(operators);
    assert.equal(hash, '#narrow/stream/987-Florida.2C-USA');
    narrow = hashchange.parse_narrow(hash.split('/'));
    assert.deepEqual(narrow, [
        {operator: 'stream', operand: 'Florida, USA', negated: false},
    ]);
}());

(function test_people_slugs() {
    var operators;
    var hash;
    var narrow;

    var alice = {
        email: 'alice@example.com',
        user_id: 42,
        full_name: 'Alice Smith',
    };

    people.add(alice);
    operators = [
        {operator: 'sender', operand: 'alice@example.com'},
    ];
    hash = hashchange.operators_to_hash(operators);
    assert.equal(hash, '#narrow/sender/42-alice');
    narrow = hashchange.parse_narrow(hash.split('/'));
    assert.deepEqual(narrow, [
        {operator: 'sender', operand: 'alice@example.com', negated: false},
    ]);

    operators = [
        {operator: 'pm-with', operand: 'alice@example.com'},
    ];
    hash = hashchange.operators_to_hash(operators);
    assert.equal(hash, '#narrow/pm-with/42-alice');
}());
