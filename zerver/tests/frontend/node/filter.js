var assert = require('assert');

(function set_up_dependencies () {
    global._ = require('third/underscore/underscore.js');

    global.util = require('js/util.js');
    global.Dict = require('js/dict.js');
    // An upcoming change is to put Filter in its own module, but
    // for now it still lives in narrow.js.  (I'm waiting for a big
    // commit from Zev to hit master first.  Once that happens,
    // I will make js/filter.js, update the references here, and
    // hopefully remember to delete this comment.)
    global.narrow = require('js/narrow.js');
    global.$ = function () {}; // for subs.js to load
    global.subs = require('js/subs.js');
    global.page_params = {
        domain: 'zulip.com'
    };
}());

var Filter = global.narrow.Filter;

(function test_basics() {
    var operators = [['stream', 'foo'], ['topic', 'bar']];
    var filter = new Filter(operators);

    assert.deepEqual(filter.operators(), operators);

    var predicate = filter.predicate();
    assert(predicate({type: 'stream', stream: 'foo', subject: 'bar'}));
    assert(!predicate({type: 'stream', stream: 'foo', subject: 'whatever'}));

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


