"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const linkifiers = zrequire("linkifiers");

linkifiers.initialize([]);

function get_linkifier_regexes() {
    return [...linkifiers.get_linkifier_map().keys()];
}

run_test("compile_linkifier", () => {
    // Verify basic pattern compilation with RE2JS.
    linkifiers.update_linkifier_rules([
        {
            pattern: "TICKET-(?P<id>\\d+)",
            url_template: "http://example1.example.com/{id}",
            id: 10,
        },
    ]);
    let regexes = get_linkifier_regexes();
    assert.equal(regexes.length, 1);
    let matcher = regexes[0].matcher(" TICKET-42 ");
    assert.ok(matcher.find());
    assert.equal(matcher.group(2), "TICKET-42");
    assert.equal(matcher.group("id"), "42");

    // Test case with multiple named groups.
    linkifiers.update_linkifier_rules([
        {
            pattern: "#cf(?P<contest>\\d+)(?P<problem>[A-Z][\\dA-Z]*)",
            url_template: "http://example3.example.com",
            id: 30,
        },
    ]);
    regexes = get_linkifier_regexes();
    assert.equal(regexes.length, 1);
    matcher = regexes[0].matcher(" #cf100Z ");
    assert.ok(matcher.find());
    assert.equal(matcher.group(2), "#cf100Z");
    assert.equal(matcher.group("contest"), "100");
    assert.equal(matcher.group("problem"), "Z");

    // Boundary matching: linkifier only matches after boundary characters.
    matcher = regexes[0].matcher("x#cf100Z ");
    assert.ok(!matcher.find());
    matcher = regexes[0].matcher("(#cf100Z)");
    assert.ok(matcher.find());
    assert.equal(matcher.group(2), "#cf100Z");

    // Test incorrect syntaxes

    // Just absolute garbage:
    blueslip.expect("error", "Failed to compile linkifier!", 1);
    linkifiers.update_linkifier_rules([
        {
            pattern: "!@#@(!#&((!&(@#(",
            url_template: "http://example4.example.com",
            id: 40,
        },
    ]);
    blueslip.reset();
    assert.deepEqual(get_linkifier_regexes(), []);

    // Python-only inline flags like (?L) are rejected by RE2JS.
    blueslip.expect("error", "Failed to compile linkifier!", 1);
    linkifiers.update_linkifier_rules([
        {
            pattern: "(?L)foo",
            url_template: "http://example2.example.com",
            id: 20,
        },
    ]);
    blueslip.reset();
    assert.deepEqual(get_linkifier_regexes(), []);
});
