const FoldDict = zrequire('fold_dict').FoldDict;
set_global('blueslip', global.make_zblueslip());

run_test('basic', () => {
    const d = new FoldDict();

    assert(d.is_empty());

    assert.deepEqual(d.keys(), []);

    d.set('foo', 'bar');
    assert.equal(d.get('foo'), 'bar');
    assert(!d.is_empty());

    d.set('foo', 'baz');
    assert.equal(d.get('foo'), 'baz');
    assert.equal(d.size, 1);

    d.set('bar', 'qux');
    assert.equal(d.get('foo'), 'baz');
    assert.equal(d.get('bar'), 'qux');
    assert.equal(d.size, 2);

    assert.equal(d.has('bar'), true);
    assert.equal(d.has('baz'), false);

    assert.deepEqual(d.keys(), ['foo', 'bar']);
    assert.deepEqual(d.values(), ['baz', 'qux']);
    assert.deepEqual(d.items(), [['foo', 'baz'], ['bar', 'qux']]);

    d.delete('bar');
    assert.equal(d.has('bar'), false);
    assert.strictEqual(d.get('bar'), undefined);

    assert.deepEqual(d.keys(), ['foo']);

    const val = ['foo'];
    const res = d.set('abc', val);
    assert.strictEqual(res, d);
});

run_test('case insensitivity', () => {
    const d = new FoldDict();

    assert.deepEqual(d.keys(), []);

    assert(!d.has('foo'));
    d.set('fOO', 'Hello World');
    assert.equal(d.get('foo'), 'Hello World');
    assert(d.has('foo'));
    assert(d.has('FOO'));
    assert(!d.has('not_a_key'));

    assert.deepEqual(d.keys(), ['fOO']);

    d.delete('Foo');
    assert.equal(d.has('foo'), false);

    assert.deepEqual(d.keys(), []);
});

run_test('clear', () => {
    const d = new FoldDict();

    function populate() {
        d.set('fOO', 1);
        assert.equal(d.get('foo'), 1);
        d.set('bAR', 2);
        assert.equal(d.get('bar'), 2);
    }

    populate();
    assert.equal(d.size, 2);
    assert(!d.is_empty());

    d.clear();
    assert.equal(d.get('fOO'), undefined);
    assert.equal(d.get('bAR'), undefined);
    assert.equal(d.size, 0);
    assert(d.is_empty());

    // make sure it still works after clearing
    populate();
    assert.equal(d.size, 2);
});

run_test('undefined_keys', () => {
    blueslip.set_test_data('error', 'Tried to call a FoldDict method with an undefined key.');

    const d = new FoldDict();

    assert.equal(d.has(undefined), false);
    assert.strictEqual(d.get(undefined), undefined);
    assert.equal(blueslip.get_test_logs('error').length, 2);

    blueslip.clear_test_data();
});

