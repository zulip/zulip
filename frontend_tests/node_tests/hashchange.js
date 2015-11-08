var hashchange = require('js/hashchange.js');

(function test_basics() {
    var operators;
    var hash;

    operators = [
        {operator: 'stream', operand: 'devel'},
        {operator: 'topic', operand: 'algol'}
    ];
    hash = hashchange.operators_to_hash(operators);
    assert.equal(hash, '#narrow/stream/devel/topic/algol');

    operators = [
        {operator: 'stream', operand: 'devel'},
        {operator: 'topic', operand: 'visual c++', negated: true}
    ];
    hash = hashchange.operators_to_hash(operators);
    assert.equal(hash, '#narrow/stream/devel/-topic/visual.20c.2B.2B');
}());
