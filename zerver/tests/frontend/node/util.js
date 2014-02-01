var assert = require('assert');

add_dependencies({
    util: 'js/util.js'
});

set_global('$', {});

var util = global.util;

(function test_CachedValue() {
    var x = 5;

    var cv = new util.CachedValue({
        compute_value: function () {
            return x * 2;
        }
    });

    assert.equal(cv.get(), 10);

    x = 6;
    assert.equal(cv.get(), 10);
    cv.reset();
    assert.equal(cv.get(), 12);

}());

(function test_lower_bound() {
    var arr = [10, 20, 30, 40, 50];
    assert.equal(util.lower_bound(arr, 5), 0);
    assert.equal(util.lower_bound(arr, 10), 0);
    assert.equal(util.lower_bound(arr, 15), 1);
    assert.equal(util.lower_bound(arr, 50), 4);
    assert.equal(util.lower_bound(arr, 55), 5);
    assert.equal(util.lower_bound(arr, 2, 4, 31), 3);

    arr = [{x: 10}, {x: 20}, {x:30}];

    function compare (a, b) {
        return a.x < b;
    }

    assert.equal(util.lower_bound(arr, 5, compare), 0);
    assert.equal(util.lower_bound(arr, 10, compare), 0);
    assert.equal(util.lower_bound(arr, 15, compare), 1);

}());

(function test_same_recipient() {
    assert(util.same_recipient(
        {type: 'stream', stream: 'Foo', subject: 'Bar'},
        {type: 'stream', stream: 'fOO', subject: 'bar'}
    ));

    assert(!util.same_recipient(
        {type: 'stream', stream: 'Foo', subject: 'Bar'},
        {type: 'stream', stream: 'yo', subject: 'whatever'}
    ));

    assert(util.same_recipient(
        {type: 'private', reply_to: 'fred@zulip.com,melissa@zulip.com'},
        {type: 'private', reply_to: 'fred@zulip.com,melissa@zulip.com'}
    ));

    assert(!util.same_recipient(
        {type: 'private', reply_to: 'fred@zulip.com'},
        {type: 'private', reply_to: 'Fred@zulip.com'}
    ));
}());

(function test_recipient_key() {
    var message;

    message = {type: 'stream', stream: 'Foo', subject: 'BAR'};
    assert.equal(util.recipient_key(message), 'foo>bar');

    global.$.trim = function (s) {
        return s.trim();
    };
    message = {type: 'private', reply_to: ' bob@example.com, alice@example.com '};
    assert.equal(util.recipient_key(message), 'alice@example.com,bob@example.com');

}());

(function test_robust_uri_decode() {
    assert.equal(util.robust_uri_decode('xxx%3Ayyy'), 'xxx:yyy');
    assert.equal(util.robust_uri_decode('xxx%3'), 'xxx');
}());


(function test_array_compare() {
    assert(util.array_compare([], []));
    assert(util.array_compare([1,2,3], [1,2,3]));
    assert(!util.array_compare([1,2], [1,2,3]));
    assert(!util.array_compare([1,2,3], [1,2]));
}());

(function test_enforce_arity() {
    function f1() {}
    var eaf1 = util.enforce_arity(f1);

    assert.doesNotThrow(function () { f1('foo'); });
    assert.doesNotThrow(function () { eaf1(); });
    assert.throws(function () { eaf1('foo'); }, /called with \d+ arguments/);
    assert.throws(function () { eaf1('foo', 'bar'); }, /called with \d+ arguments/);

    function f2(x) {}
    var eaf2 = util.enforce_arity(f2);

    assert.doesNotThrow(function () { f2(); });
    assert.doesNotThrow(function () { eaf2('foo'); });
    assert.throws(function () { eaf2(); }, /called with \d+ arguments/);
    assert.throws(function () { eaf2('foo', 'bar'); }, /called with \d+ arguments/);

    function f3(x, y) {}
    var eaf3 = util.enforce_arity(f3);

    assert.doesNotThrow(function () { f3(); });
    assert.doesNotThrow(function () { eaf3('foo', 'bar'); });
    assert.throws(function () { eaf3(); }, /called with \d+ arguments/);
    assert.throws(function () { eaf3('foo'); }, /called with \d+ arguments/);
    assert.throws(function () { eaf3('foo','bar', 'baz'); }, /called with \d+ arguments/);
}());
