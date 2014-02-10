add_dependencies({
    util: 'js/util.js',
    stream_data: 'js/stream_data.js'
});

set_global('page_params', {
    email: 'hamlet@zulip.com',
    domain: 'zulip.com'
});
set_global('feature_flags', {
    remove_filter_tuples_safety_net: false
});

var Filter = require('js/filter.js');
var _ = global._;

function assert_same_operators(result, terms) {
    result = _.map(result, function (term) {
        return {
            operator: term.operator,
            operand: term.operand
        };
    });
    assert.deepEqual(result, terms);
}

(function test_basics() {
    var operators = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'topic', operand: 'bar'}
    ];
    var filter = new Filter(operators);

    assert_same_operators(filter.operators(), operators);
    assert.deepEqual(filter.operands('stream'), ['foo']);

    assert(filter.has_operator('stream'));
    assert(!filter.has_operator('search'));

    assert(filter.has_operand('stream', 'foo'));
    assert(!filter.has_operand('stream', 'nada'));

    assert(!filter.is_search());
    assert(filter.can_apply_locally());

    operators = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'topic', operand: 'bar'},
        {operator: 'search', operand: 'pizza'}
    ];
    filter = new Filter(operators);

    assert(filter.is_search());
    assert(! filter.can_apply_locally());
}());

(function test_new_style_operators() {
    var term = {
        operator: 'stream',
        operand: 'foo'
    };
    var operators = [term];
    var filter = new Filter(operators);

    assert.deepEqual(filter.operands('stream'), ['foo']);
}());

(function test_public_operators() {
    var operators = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'topic', operand: 'bar'}
    ];

    var filter = new Filter(operators);
    assert_same_operators(filter.public_operators(), operators);

    operators = [
        {operator: 'in', operand: 'all'}
    ];
    filter = new Filter(operators);
    assert_same_operators(filter.public_operators(), []);
}());

(function test_canonicalizations() {
    assert.equal(Filter.canonicalize_operator('Is'), 'is');
    assert.equal(Filter.canonicalize_operator('Stream'), 'stream');
    assert.equal(Filter.canonicalize_operator('Subject'), 'topic');

    var term;
    term = Filter.canonicalize_term({operator: 'Stream', operand: 'Denmark'});
    assert.equal(term.operator, 'stream');
    assert.equal(term.operand, 'Denmark');

    term = Filter.canonicalize_term({operator: 'sender', operand: 'me'});
    assert.equal(term.operator, 'sender');
    assert.equal(term.operand, 'hamlet@zulip.com');

    term = Filter.canonicalize_term({operator: 'pm-with', operand: 'me'});
    assert.equal(term.operator, 'pm-with');
    assert.equal(term.operand, 'hamlet@zulip.com');

    term = Filter.canonicalize_term({operator: 'search', operand: 'foo'});
    assert.equal(term.operator, 'search');
    assert.equal(term.operand, 'foo');

    term = Filter.canonicalize_term({operator: 'search', operand: 'fOO'});
    assert.equal(term.operator, 'search');
    assert.equal(term.operand, 'foo');

    term = Filter.canonicalize_term({operator: 'search', operand: 123});
    assert.equal(term.operator, 'search');
    assert.equal(term.operand, '123');

    term = Filter.canonicalize_term({operator: 'search', operand: 'abc “xyz”'});
    assert.equal(term.operator, 'search');
    assert.equal(term.operand, 'abc "xyz"');
}());

function get_predicate(operators) {
    operators = _.map(operators, function (op) {
        return {operator: op[0], operand: op[1]};
    });
    return new Filter(operators).predicate();
}

(function test_predicate_basics() {
    // Predicates are functions that accept a message object with the message
    // attributes (not content), and return true if the message belongs in a
    // given narrow. If the narrow parameters include a search, the predicate
    // passes through all messages.
    //
    // To keep these tests simple, we only pass objects with a few relevant attributes
    // rather than full-fledged message objects.
    var predicate = get_predicate([['stream', 'Foo'], ['topic', 'Bar']]);
    assert(predicate({type: 'stream', stream: 'foo', subject: 'bar'}));
    assert(!predicate({type: 'stream', stream: 'foo', subject: 'whatever'}));
    assert(!predicate({type: 'stream', stream: 'wrong'}));
    assert(!predicate({type: 'private'}));

    predicate = get_predicate([['search', 'emoji']]);
    assert(predicate({}));

    predicate = get_predicate([['topic', 'Bar']]);
    assert(!predicate({type: 'private'}));

    predicate = get_predicate([['is', 'private']]);
    assert(predicate({type: 'private'}));
    assert(!predicate({type: 'stream'}));

    predicate = get_predicate([['is', 'starred']]);
    assert(predicate({starred: true}));
    assert(!predicate({starred: false}));

    predicate = get_predicate([['is', 'alerted']]);
    assert(predicate({alerted: true}));
    assert(!predicate({alerted: false}));
    assert(!predicate({}));

    predicate = get_predicate([['is', 'mentioned']]);
    assert(predicate({mentioned: true}));
    assert(!predicate({mentioned: false}));

    predicate = get_predicate([['in', 'all']]);
    assert(predicate({}));

    predicate = get_predicate([['in', 'home']]);
    assert(!predicate({stream: 'unsub'}));
    assert(predicate({type: 'private'}));

    predicate = get_predicate([['near', 5]]);
    assert(predicate({}));

    predicate = get_predicate([['id', 5]]);
    assert(predicate({id: 5}));
    assert(!predicate({id: 6}));

    predicate = get_predicate([['id', 5], ['topic', 'lunch']]);
    assert(predicate({type: 'stream', id: 5, subject: 'lunch'}));
    assert(!predicate({type: 'stream', id: 5, subject: 'dinner'}));

    predicate = get_predicate([['sender', 'Joe@example.com']]);
    assert(predicate({sender_email: 'JOE@example.com'}));
    assert(!predicate({sender_email: 'steve@foo.com'}));

    predicate = get_predicate([['pm-with', 'Joe@example.com']]);
    assert(predicate({type: 'private', reply_to: 'JOE@example.com'}));
    assert(!predicate({type: 'private', reply_to: 'steve@foo.com'}));
}());


(function test_mit_exceptions() {
    global.page_params.domain = 'mit.edu';

    var predicate = get_predicate([['stream', 'Foo'], ['topic', 'personal']]);
    assert(predicate({type: 'stream', stream: 'foo', subject: 'personal'}));
    assert(predicate({type: 'stream', stream: 'foo.d', subject: 'personal'}));
    assert(predicate({type: 'stream', stream: 'foo.d', subject: ''}));
    assert(!predicate({type: 'stream', stream: 'wrong'}));
    assert(!predicate({type: 'stream', stream: 'foo', subject: 'whatever'}));
    assert(!predicate({type: 'private'}));

    predicate = get_predicate([['stream', 'Foo'], ['topic', 'bar']]);
    assert(predicate({type: 'stream', stream: 'foo', subject: 'bar.d'}));

    // Try to get the MIT regex to explode for an empty stream.
    var terms = [
        {operator: 'stream', operand: ''},
        {operator: 'topic', operand: 'bar'}
    ];
    predicate = new Filter(terms).predicate();
    assert(!predicate({type: 'stream', stream: 'foo', subject: 'bar'}));

    // Try to get the MIT regex to explode for an empty topic.
    terms = [
        {operator: 'stream', operand: 'foo'},
        {operator: 'topic', operand: ''}
    ];
    predicate = new Filter(terms).predicate();
    assert(!predicate({type: 'stream', stream: 'foo', subject: 'bar'}));
}());

(function test_predicate_edge_cases() {
    // The code supports undefined as an operator to Filter, which results
    // in a predicate that accepts any message.
    var predicate = get_predicate();
    assert(predicate({}));

    // Upstream code should prevent Filter.predicate from being called with
    // invalid operator/operand combinations, but right now we just silently
    // return a function that accepts all messages.
    predicate = get_predicate([['in', 'bogus']]);
    assert(predicate({}));

    predicate = get_predicate([['bogus', 33]]);
    assert(predicate({}));

    predicate = get_predicate([['is', 'bogus']]);
    assert(predicate({}));

    // Exercise caching feature.
    var terms = [
        {operator: 'stream', operand: 'Foo'},
        {operator: 'topic', operand: 'bar'}
    ];
    var filter = new Filter(terms);
    predicate = filter.predicate();
    predicate = filter.predicate(); // get cached version
    assert(predicate({type: 'stream', stream: 'foo', subject: 'bar'}));

}());

(function test_parse() {
    var string;
    var operators;

    function _test() {
        var result = Filter.parse(string);
        assert_same_operators(result, operators);
    }

    string ='stream:Foo topic:Bar yo';
    operators = [
        {operator: 'stream', operand: 'Foo'},
        {operator: 'topic', operand: 'Bar'},
        {operator: 'search', operand: 'yo'}
    ];
    _test();

    string = 'pm-with:leo+test@zulip.com';
    operators = [
        {operator: 'pm-with', operand: 'leo+test@zulip.com'}
    ];
    _test();

    string = 'sender:leo+test@zulip.com';
    operators = [
        {operator: 'sender', operand: 'leo+test@zulip.com'}
    ];
    _test();

    string = 'stream:With+Space';
    operators = [
        {operator: 'stream', operand: 'With Space'}
    ];
    _test();
}());

(function test_unparse() {
    var string;
    var operators;

    operators = [
        {operator: 'stream', operand: 'Foo'},
        {operator: 'topic', operand: 'Bar'},
        {operator: 'search', operand: 'yo'}
    ];
    string = 'stream:Foo topic:Bar yo';
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [
        {operator: 'id', operand: 50}
    ];
    string = 'id:50';
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [
        {operator: 'near', operand: 150}
    ];
    string = 'near:150';
    assert.deepEqual(Filter.unparse(operators), string);
}());
