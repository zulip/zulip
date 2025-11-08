"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const {LazySet} = zrequire("lazy_set");

/*
    We mostly test LazySet indirectly.  This code
    may be short-lived, anyway, once we change
    how we download subscribers in page_params.
*/

run_test("map", () => {
    const ls = new LazySet([1, 2]);

    assert.deepEqual(
        ls.map((n) => n * 3),
        [3, 6],
    );
});

run_test("size", () => {
    const ls = new LazySet([1, 2]);
    assert.deepEqual(ls.size, 2);

    ls._make_set();
    assert.deepEqual(ls.size, 2);
});

run_test("conversions", () => {
    blueslip.expect("error", "not a number", 2);
    const ls = new LazySet([1, 2]);
    ls.add("3");
    assert.ok(ls.has("3"));
});
