"use strict";

const {strict: assert} = require("assert");

const {use} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const {
    lazy_set: {LazySet},
} = use("lazy_set");

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

run_test("conversions", () => {
    blueslip.expect("error", "not a number", 2);
    const ls = new LazySet([1, 2]);
    ls.add("3");
    assert(ls.has("3"));
});
