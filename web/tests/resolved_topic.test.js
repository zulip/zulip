"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const resolved_topic = zrequire("../shared/src/resolved_topic");

const topic_name = "asdf";
const resolved_name = "✔ " + topic_name;
const overresolved_name = "✔ ✔✔ " + topic_name;
const pseudoresolved_name = "✔" + topic_name; // check mark, but no space
const names = [topic_name, resolved_name, overresolved_name, pseudoresolved_name];

run_test("is_resolved", () => {
    assert.ok(!resolved_topic.is_resolved(topic_name));
    assert.ok(resolved_topic.is_resolved(resolved_name));
    assert.ok(resolved_topic.is_resolved(overresolved_name));
    assert.ok(!resolved_topic.is_resolved(pseudoresolved_name));
});

run_test("resolve_name", () => {
    assert.equal(resolved_topic.resolve_name(topic_name), resolved_name);

    for (const name of names) {
        assert.notEqual(resolved_topic.resolve_name(name), name);
    }
});

run_test("unresolve_name", () => {
    assert.equal(resolved_topic.unresolve_name(topic_name), topic_name);
    assert.equal(resolved_topic.unresolve_name(resolved_name), topic_name);
    assert.equal(resolved_topic.unresolve_name(overresolved_name), topic_name);
    assert.equal(resolved_topic.unresolve_name(pseudoresolved_name), pseudoresolved_name);
});

run_test("display_parts", () => {
    const results = [];
    for (const name of names) {
        const [prefix, display_name] = resolved_topic.display_parts(name);

        // The parts always partition the input name.
        assert.equal(prefix + display_name, name);

        // The prefix is always the canonical prefix, or empty…
        assert.ok(prefix === "" || prefix === resolved_topic.RESOLVED_TOPIC_PREFIX);
        // … and which one is determined by is_resolved.
        assert.equal(Boolean(prefix), resolved_topic.is_resolved(name));

        // The parts, together, differ from those of any other input.
        // (Yes, this is quadratic.  Keep the list of test data nice and short.)
        assert.ok(!results.some(([p, d]) => p === prefix && d === display_name));
        results.push([prefix, display_name]);
    }
});
