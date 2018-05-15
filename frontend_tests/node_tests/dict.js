set_global('blueslip', global.make_zblueslip());

run_test('basic', () => {
    var d = new Dict();

    assert(d.is_empty());

    assert.deepEqual(d.keys(), []);

    d.set('foo', 'bar');
    assert.equal(d.get('foo'), 'bar');
    assert(!d.is_empty());

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

    var val = ['foo'];
    var res = d.set('abc', val);
    assert.equal(val, res);
});

run_test('fold_case', () => {
    var d = new Dict({fold_case: true});

    assert.deepEqual(d.keys(), []);

    assert(!d.has('foo'));
    d.set('fOO', 'Hello World');
    assert.equal(d.get('foo'), 'Hello World');
    assert(d.has('foo'));
    assert(d.has('FOO'));
    assert(!d.has('not_a_key'));

    assert.deepEqual(d.keys(), ['fOO']);

    d.del('Foo');
    assert.equal(d.has('foo'), false);

    assert.deepEqual(d.keys(), []);
});

run_test('undefined_keys', () => {
    blueslip.set_test_data('error', 'Tried to call a Dict method with an undefined key.');

    var d = new Dict();

    assert.equal(d.has(undefined), false);
    assert.strictEqual(d.get(undefined), undefined);

    d = new Dict({fold_case: true});

    assert.equal(d.has(undefined), false);
    assert.strictEqual(d.get(undefined), undefined);
    assert.equal(blueslip.get_test_logs('error').length, 4);

    blueslip.clear_test_data();
});

run_test('restricted_keys', () => {
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
});

run_test('construction', () => {
    var d1 = new Dict();

    assert.deepEqual(d1.items(), []);

    var d2 = Dict.from({foo: 'bar', baz: 'qux'});
    assert.deepEqual(d2.items(), [['foo', 'bar'], ['baz', 'qux']]);

    var d3 = d2.clone();
    d3.del('foo');
    assert.deepEqual(d2.items(), [['foo', 'bar'], ['baz', 'qux']]);
    assert.deepEqual(d3.items(), [['baz', 'qux']]);

    var d4 = Dict.from_array(['foo', 'bar']);
    assert.deepEqual(d4.items(), [['foo', true], ['bar', true]]);

    var caught;
    try {
        Dict.from('bogus');
    } catch (e) {
        caught = true;
        assert.equal(e.toString(), 'TypeError: Cannot convert argument to Dict');
    }
    assert(caught);

    caught = undefined;
    try {
        Dict.from_array({bogus: true});
    } catch (e2) {
        caught = true;
        assert.equal(e2.toString(), 'TypeError: Argument is not an array');
    }
    assert(caught);
});

run_test('each', () => {
    var d = new Dict();
    d.set('apple', 40);
    d.set('banana', 50);
    d.set('carrot', 60);

    var unseen_keys = d.keys();

    var cnt = 0;
    d.each(function (v, k) {
        assert.equal(v, d.get(k));
        unseen_keys = _.without(unseen_keys, k);
        cnt += 1;
    });

    assert.equal(cnt, d.keys().length);
    assert.equal(unseen_keys.length, 0);
});

run_test('setdefault', () => {
    var d = new Dict();
    var val = ['foo'];
    var res = d.setdefault('foo', val);
    assert.equal(res, val);
    assert.equal(d.has('foo'), true);
    assert.equal(d.get('foo'), val);

    var val2 = ['foo2'];
    res = d.setdefault('foo', val2);
    assert.equal(res, val);
    assert.equal(d.get('foo'), val);
});

run_test('num_items', () => {
    var d = new Dict();
    assert.equal(d.num_items(), 0);
    assert(d.is_empty());

    d.set('foo', 1);
    assert.equal(d.num_items(), 1);
    assert(!d.is_empty());

    d.set('foo', 2);
    assert.equal(d.num_items(), 1);
    assert(!d.is_empty());

    d.set('bar', 1);
    assert.equal(d.num_items(), 2);
    d.del('foo');
    assert.equal(d.num_items(), 1);
});

run_test('clear', () => {
    var d = new Dict();

    function populate() {
        d.set('foo', 1);
        assert.equal(d.get('foo'), 1);
        d.set('bar', 2);
        assert.equal(d.get('bar'), 2);
    }

    populate();
    assert.equal(d.num_items(), 2);
    assert(!d.is_empty());

    d.clear();
    assert.equal(d.get('foo'), undefined);
    assert.equal(d.get('bar'), undefined);
    assert.equal(d.num_items(), 0);
    assert(d.is_empty());

    // make sure it still works after clearing
    populate();
    assert.equal(d.num_items(), 2);
});
