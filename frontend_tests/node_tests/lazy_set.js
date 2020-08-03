"use strict";

const {LazySet} = zrequire("lazy_set");

/*
    We mostly test LazySet indirectly.  This code
    may be short-lived, anyway, once we change
    how we download subscribers in page_params.
*/

run_test("map", () => {
    const ls = new LazySet([1, 2]);

    const triple = (n) => n * 3;

    assert.deepEqual(ls.map(triple), [3, 6]);
});

run_test("conversions", () => {
    blueslip.expect("error", "not a number", 2);
    const ls = new LazySet([1, 2]);
    ls.add("3");
    assert(ls.has("3"));
});
