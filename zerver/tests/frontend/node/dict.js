global._ = require('third/underscore/underscore.js');
global.util = require('js/util.js');
var Dict = require('js/dict.js');
var assert = require('assert');

(function test_basic() {
    var d = new Dict();

    assert.deepEqual(d.keys(), []);

    d.set('foo', 'bar');
    assert.equal(d.get('foo'), 'bar');

    d.set('foo', 'baz');
    assert.equal(d.get('foo'), 'baz');

    d.set('bar', 'qux');
    assert.equal(d.get('foo'), 'baz');
    assert.equal(d.get('bar'), 'qux');

    assert.equal(d.has('bar'), true);
    assert.equal(d.has('baz'), false);

    assert.deepEqual(d.keys(), ['foo', 'bar']);
    assert.deepEqual(d.values(), ['baz', 'qux']);
    assert.deepEqual(d.items(), [['foo', 'baz'], ['bar', 'qux']]);

    d.del('bar');
    assert.equal(d.has('bar'), false);
    assert.strictEqual(d.get('bar'), undefined);

    assert.deepEqual(d.keys(), ['foo']);
}());

(function test_restricted_keys() {
    var d = new Dict();

    assert.equal(d.has('__proto__'), false);
    assert.equal(d.has('hasOwnProperty'), false);
    assert.equal(d.has('toString'), false);

    assert.strictEqual(d.get('__proto__'), undefined);
    assert.strictEqual(d.get('hasOwnProperty'), undefined);
    assert.strictEqual(d.get('toString'), undefined);

    d.set('hasOwnProperty', function () {return true;});
    assert.equal(d.has('blah'), false);

    d.set('__proto__', 'foo');
    d.set('foo', 'bar');
    assert.equal(d.get('foo'), 'bar');
}());

(function test_construction() {
    var d1 = new Dict();

    assert.deepEqual(d1.items(), []);

    var d2 = new Dict({foo: 'bar', baz: 'qux'});
    assert.deepEqual(d2.items(), [['foo', 'bar'], ['baz', 'qux']]);

    var d3 = new Dict(d2);
    d3.del('foo');
    assert.deepEqual(d2.items(), [['foo', 'bar'], ['baz', 'qux']]);
    assert.deepEqual(d3.items(), [['baz', 'qux']]);
}());
