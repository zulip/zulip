add_dependencies({
    hash_util: 'js/hash_util.js',
    people: 'js/people.js',
});

var hashchange = require('js/hashchange.js');


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
