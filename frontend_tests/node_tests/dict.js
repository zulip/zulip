set_global('blueslip', global.make_zblueslip());
const Dict = zrequire('dict').Dict;

run_test('basic', () => {
    const d = new Dict();

    assert.equal(d.size, 0);

    assert.deepEqual([...d.keys()], []);

    d.set('foo', 'bar');
    assert.equal(d.get('foo'), 'bar');
    assert.notEqual(d.size, 0);

    d.set('foo', 'baz');
    assert.equal(d.get('foo'), 'baz');
    assert.equal(d.size, 1);

    d.set('bar', 'qux');
    assert.equal(d.get('foo'), 'baz');
    assert.equal(d.get('bar'), 'qux');
    assert.equal(d.size, 2);

    assert.equal(d.has('bar'), true);
    assert.equal(d.has('baz'), false);

    assert.deepEqual([...d.keys()], ['foo', 'bar']);
    assert.deepEqual([...d.values()], ['baz', 'qux']);
    assert.deepEqual([...d], [['foo', 'baz'], ['bar', 'qux']]);

    d.delete('bar');
    assert.equal(d.has('bar'), false);
    assert.strictEqual(d.get('bar'), undefined);

    assert.deepEqual([...d.keys()], ['foo']);

    const val = ['foo'];
    const res = d.set('abc', val);
    assert.strictEqual(res, d);
});

run_test('undefined_keys', () => {
    blueslip.clear_test_data();
    blueslip.set_test_data('error', 'Tried to call a Dict method with an undefined key.');

    const d = new Dict();

    assert.equal(d.has(undefined), false);
    assert.strictEqual(d.get(undefined), undefined);
    assert.equal(blueslip.get_test_logs('error').length, 2);
});

run_test('non-strings', () => {
    blueslip.clear_test_data();
    blueslip.set_test_data('error', 'Tried to call a Dict method with a non-string.');

    const d = new Dict();

    d.set('17', 'value');
    assert.equal(d.get(17), 'value');
    assert.equal(blueslip.get_test_logs('error').length, 1);
});

run_test('restricted_keys', () => {
    const d = new Dict();

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
    const d1 = new Dict();

    assert.deepEqual([...d1], []);

    const d2 = new Dict();
    d2.set('foo', 'bar');
    d2.set('baz', 'qux');
    assert.deepEqual([...d2], [['foo', 'bar'], ['baz', 'qux']]);
});

run_test('each', () => {
    const d = new Dict();
    d.set('apple', 40);
    d.set('banana', 50);
    d.set('carrot', 60);

    let unseen_keys = [...d.keys()];

    let cnt = 0;
    d.each(function (v, k) {
        assert.equal(v, d.get(k));
        unseen_keys = _.without(unseen_keys, k);
        cnt += 1;
    });

    assert.equal(cnt, d.size);
    assert.equal(unseen_keys.length, 0);
});

run_test('num_items', () => {
    const d = new Dict();
    assert.equal(d.size, 0);

    d.set('foo', 1);
    assert.equal(d.size, 1);

    d.set('foo', 2);
    assert.equal(d.size, 1);

    d.set('bar', 1);
    assert.equal(d.size, 2);
    d.delete('foo');
    assert.equal(d.size, 1);
});

/*
run_test('benchmark', () => {
    const d = new Dict();
    const n = 5000;
    const t1 = new Date().getTime();

    _.each(_.range(n), (i) => {
        d.set(i, i);
    });

    _.each(_.range(n), (i) => {
        d.get(i, i);
    });

    const t2 = new Date().getTime();
    const elapsed = t2 - t1;
    console.log('elapsed (milli)', elapsed);
    console.log('per (micro)', 1000 * elapsed / n);
});
*/

run_test('clear', () => {
    const d = new Dict();

    function populate() {
        d.set('foo', 1);
        assert.equal(d.get('foo'), 1);
        d.set('bar', 2);
        assert.equal(d.get('bar'), 2);
    }

    populate();
    assert.equal(d.size, 2);

    d.clear();
    assert.equal(d.get('foo'), undefined);
    assert.equal(d.get('bar'), undefined);
    assert.equal(d.size, 0);

    // make sure it still works after clearing
    populate();
    assert.equal(d.size, 2);
});
