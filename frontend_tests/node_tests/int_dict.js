set_global('blueslip', global.make_zblueslip());
const IntDict = zrequire('int_dict').IntDict;

run_test('basic', () => {
    const d = new IntDict();

    assert(d.is_empty());

    assert.deepEqual(d.keys(), []);

    d.set(101, 'bar');
    assert.equal(d.get(101), 'bar');
    assert(!d.is_empty());

    d.set(101, 'baz');
    assert.equal(d.get(101), 'baz');
    assert.equal(d.num_items(), 1);

    d.set(102, 'qux');
    assert.equal(d.get(101), 'baz');
    assert.equal(d.get(102), 'qux');
    assert.equal(d.num_items(), 2);

    assert.equal(d.has(102), true);
    assert.equal(d.has(999), false);

    assert.deepEqual(d.keys(), [101, 102]);
    assert.deepEqual(d.values(), ['baz', 'qux']);

    d.delete(102);
    assert.equal(d.has(102), false);
    assert.strictEqual(d.get(102), undefined);

    assert.deepEqual(d.keys(), [101]);

    const val = ['fred'];
    const res = d.set(103, val);
    assert.strictEqual(res, d);
});


run_test('each', () => {
    const d = new IntDict();
    d.set(4, 40);
    d.set(5, 50);
    d.set(6, 60);

    let unseen_keys = d.keys();

    let cnt = 0;
    d.each(function (v, k) {
        assert.equal(v, d.get(k));
        unseen_keys = _.without(unseen_keys, k);
        cnt += 1;
    });

    assert.equal(cnt, d.keys().length);
    assert.equal(unseen_keys.length, 0);
});

/*
run_test('benchmark', () => {
    const d = new IntDict();
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

run_test('filter_values', () => {
    const d = new IntDict();

    d.set(1, "fred");
    d.set(2, "foo");
    d.set(3, "bar");
    d.set(4, "baz");
    d.set(4, "fay");

    const pred = (v) => {
        return v.startsWith('f');
    };

    assert.deepEqual(d.filter_values(pred).sort(), ['fay', 'foo', 'fred']);
});

run_test('undefined_keys', () => {
    blueslip.clear_test_data();
    blueslip.set_test_data('error', 'Tried to call a IntDict method with an undefined key.');

    const d = new IntDict();

    assert.equal(d.has(undefined), false);
    assert.strictEqual(d.get(undefined), undefined);
    assert.equal(blueslip.get_test_logs('error').length, 2);
});

run_test('non integers', () => {
    blueslip.clear_test_data();
    blueslip.set_test_data('error', 'Tried to call a IntDict method with a non-integer.');

    const d = new IntDict();

    assert.equal(d.has('some-string'), false);
    assert.equal(blueslip.get_test_logs('error').length, 1);

    // verify stringified ints still work
    blueslip.clear_test_data();
    blueslip.set_test_data('error', 'Tried to call a IntDict method with a non-integer.');

    d.set('5', 'five');
    assert.equal(d.has(5), true);
    assert.equal(d.has('5'), true);

    assert.equal(d.get(5), 'five');
    assert.equal(d.get('5'), 'five');
    assert.equal(blueslip.get_test_logs('error').length, 3);
});

run_test('num_items', () => {
    const d = new IntDict();
    assert.equal(d.num_items(), 0);
    assert(d.is_empty());

    d.set(101, 1);
    assert.equal(d.num_items(), 1);
    assert(!d.is_empty());

    d.set(101, 2);
    assert.equal(d.num_items(), 1);
    assert(!d.is_empty());

    d.set(102, 1);
    assert.equal(d.num_items(), 2);
    d.delete(101);
    assert.equal(d.num_items(), 1);
});

run_test('clear', () => {
    const d = new IntDict();

    function populate() {
        d.set(101, 1);
        assert.equal(d.get(101), 1);
        d.set(102, 2);
        assert.equal(d.get(102), 2);
    }

    populate();
    assert.equal(d.num_items(), 2);
    assert(!d.is_empty());

    d.clear();
    assert.equal(d.get(101), undefined);
    assert.equal(d.get(102), undefined);
    assert.equal(d.num_items(), 0);
    assert(d.is_empty());

    // make sure it still works after clearing
    populate();
    assert.equal(d.num_items(), 2);
});
