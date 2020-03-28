set_global('blueslip', global.make_zblueslip());
const LazySet = zrequire('lazy_set').LazySet;

/*
    We mostly test LazySet indirectly.  This code
    may be short-lived, anyway, once we change
    how we download subscribers in page_params.
*/

run_test('map', () => {
    const ls = new LazySet([1, 2]);

    const triple = (n) => n * 3;

    assert.deepEqual(ls.map(triple), [3, 6]);
});

run_test('conversions', () => {
    blueslip.set_test_data('error', 'not a number');
    const ls = new LazySet([1, 2]);
    ls.add('3');
    assert(ls.has('3'));
});
