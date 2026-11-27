"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

const {localstorage} = zrequire("localstorage");

run_test("set, get and remove", () => {
    const ls = localstorage();

    assert.equal(ls.get("key"), undefined);
    assert.equal(ls.set("key", {value: 1}), true);
    assert.deepEqual(ls.get("key"), {value: 1});

    ls.remove("key");
    assert.equal(ls.get("key"), undefined);
});

run_test("failed writes still throw", ({override}) => {
    const ls = localstorage();

    override(window.localStorage, "setItem", () => {
        throw new Error("QuotaExceededError");
    });

    assert.throws(() => ls.set("key", "value"), {message: "QuotaExceededError"});
});

run_test("localStorage is null", () => {
    // set_global does not accept null.
    const real_local_storage = localStorage;
    globalThis.localStorage = null;
    try {
        const ls = localstorage();

        assert.equal(localstorage.supported(), false);
        assert.equal(ls.set("key", "value"), false);
        assert.equal(ls.get("key"), undefined);
        ls.remove("key");
        assert.equal(ls.migrate("key", 1, 2, noop), undefined);
    } finally {
        globalThis.localStorage = real_local_storage;
    }
});
