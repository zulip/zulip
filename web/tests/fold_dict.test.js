"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const {FoldDict} = zrequire("fold_dict");

run_test("basic", () => {
    const d = new FoldDict();

    assert.equal(d.size, 0);

    assert.deepEqual([...d.keys()], []);

    d.set("foo", "bar");
    assert.equal(d.get("foo"), "bar");
    assert.notEqual(d.size, 0);

    d.set("foo", "baz");
    assert.equal(d.get("foo"), "baz");
    assert.equal(d.size, 1);

    d.set("bar", "qux");
    assert.equal(d.get("foo"), "baz");
    assert.equal(d.get("bar"), "qux");
    assert.equal(d.size, 2);

    assert.equal(d.has("bar"), true);
    assert.equal(d.has("baz"), false);

    assert.deepEqual([...d.keys()], ["foo", "bar"]);
    assert.deepEqual([...d.values()], ["baz", "qux"]);
    assert.deepEqual(
        [...d],
        [
            ["foo", "baz"],
            ["bar", "qux"],
        ],
    );

    d.delete("bar");
    assert.equal(d.has("bar"), false);
    assert.strictEqual(d.get("bar"), undefined);

    assert.deepEqual([...d.keys()], ["foo"]);

    const val = ["foo"];
    const res = d.set("abc", val);
    assert.strictEqual(res, d);
});

run_test("case insensitivity", () => {
    const d = new FoldDict();

    assert.deepEqual([...d.keys()], []);

    assert.ok(!d.has("foo"));
    d.set("fOO", "Hello world");
    assert.equal(d.get("foo"), "Hello world");
    assert.ok(d.has("foo"));
    assert.ok(d.has("FOO"));
    assert.ok(!d.has("not_a_key"));

    assert.deepEqual([...d.keys()], ["fOO"]);

    d.delete("Foo");
    assert.equal(d.has("foo"), false);

    assert.deepEqual([...d.keys()], []);
});

run_test("clear", () => {
    const d = new FoldDict();

    function populate() {
        d.set("fOO", 1);
        assert.equal(d.get("foo"), 1);
        d.set("bAR", 2);
        assert.equal(d.get("bar"), 2);
    }

    populate();
    assert.equal(d.size, 2);

    d.clear();
    assert.equal(d.get("fOO"), undefined);
    assert.equal(d.get("bAR"), undefined);
    assert.equal(d.size, 0);

    // make sure it still works after clearing
    populate();
    assert.equal(d.size, 2);
});

run_test("undefined_keys", () => {
    const d = new FoldDict();

    assert.throws(() => d.has(undefined), {
        name: "TypeError",
        message: "Tried to call a FoldDict method with an undefined key.",
    });
});
