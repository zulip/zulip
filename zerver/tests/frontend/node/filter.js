var assert = require('assert');

add_dependencies({
    _: 'third/underscore/underscore.js',
    util: 'js/util.js',
    Dict: 'js/dict.js',
    stream_data: 'js/stream_data.js'
});

set_global('page_params', {
    domain: 'zulip.com'
});

var Filter = require('js/filter.js');

(function test_basics() {
    var operators = [['stream', 'foo'], ['topic', 'bar']];
    var filter = new Filter(operators);

    assert.deepEqual(filter.operators(), operators);
    assert.deepEqual(filter.operands('stream'), ['foo']);

    assert(filter.has_operator('stream'));
    assert(!filter.has_operator('search'));

    assert(filter.has_operand('stream', 'foo'));
    assert(!filter.has_operand('stream', 'nada'));

    assert(!filter.is_search());
    assert(filter.can_apply_locally());

    operators = [['stream', 'foo'], ['topic', 'bar'], ['search', 'pizza']];
    filter = new Filter(operators);

    assert(filter.is_search());
    assert(! filter.can_apply_locally());
}());

(function test_public_operators() {
    var operators = [['stream', 'foo'], ['topic', 'bar']];
    var filter = new Filter(operators);
    assert.deepEqual(filter.public_operators(), operators);

    operators = [['in', 'all']];
    filter = new Filter(operators);
    assert.deepEqual(filter.public_operators(), undefined);
}());

(function test_canonicalizations() {
    assert.equal(Filter.canonicalize_operator('Is'), 'is');
    assert.equal(Filter.canonicalize_operator('Stream'), 'stream');
    assert.equal(Filter.canonicalize_operator('Subject'), 'topic');

    assert.deepEqual(Filter.canonicalize_tuple(['Stream', 'Denmark']), ['stream', 'Denmark']);
}());

(function test_predicates() {
    // Predicates are functions that accept a message object with the message
    // attributes (not content), and return true if the message belongs in a
    // given narrow. If the narrow parameters include a search, the predicate
    // passes through all messages.
    //
    // To keep these tests simple, we only pass objects with a few relevant attributes
    // rather than full-fledged message objects.
    function get_predicate(operators) {
        return new Filter(operators).predicate();
    }

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

    predicate = get_predicate([['sender', 'Joe@example.com']]);
    assert(predicate({sender_email: 'JOE@example.com'}));
    assert(!predicate({sender_email: 'steve@foo.com'}));

    predicate = get_predicate([['pm-with', 'Joe@example.com']]);
    assert(predicate({type: 'private', reply_to: 'JOE@example.com'}));
    assert(!predicate({type: 'private', reply_to: 'steve@foo.com'}));


    global.page_params.domain = 'mit.edu';

    predicate = get_predicate([['stream', 'Foo'], ['topic', 'personal']]);
    assert(predicate({type: 'stream', stream: 'foo', subject: 'personal'}));
    assert(predicate({type: 'stream', stream: 'foo.d', subject: 'personal'}));
    assert(predicate({type: 'stream', stream: 'foo.d', subject: ''}));
    assert(!predicate({type: 'stream', stream: 'wrong'}));
    assert(!predicate({type: 'stream', stream: 'foo', subject: 'whatever'}));
    assert(!predicate({type: 'private'}));

    predicate = get_predicate([['stream', 'Foo'], ['topic', 'bar']]);
    assert(predicate({type: 'stream', stream: 'foo', subject: 'bar.d'}));

    predicate = get_predicate();
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
    var filter = new Filter([['stream', 'Foo'], ['topic', 'bar']]);
    predicate = filter.predicate();
    predicate = filter.predicate(); // get cached version
    assert(predicate({type: 'stream', stream: 'foo', subject: 'bar.d'}));

}());

(function test_parse_and_unparse() {
    var string ='stream:Foo topic:Bar yo';
    var operators = [['stream', 'Foo'], ['topic', 'Bar'], ['search', 'yo']];

    assert.deepEqual(Filter.parse(string), operators);

    string = 'stream:Foo topic:Bar yo';
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [['id', 50]];
    string = 'id:50';
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [['near', 150]];
    string = 'near:150';
    assert.deepEqual(Filter.unparse(operators), string);
}());



