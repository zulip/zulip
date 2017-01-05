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
