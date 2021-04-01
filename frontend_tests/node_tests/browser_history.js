"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");

const browser_history = zrequire("browser_history");

const location = set_global("location", {
    hash: "bogus",
});

function test(label, f) {
    run_test(label, (override) => {
        location.hash = "bogus";
        browser_history.clear_for_testing();
        f(override);
    });
}

test("basics", () => {
    const hash1 = "#settings/your-account";
    const hash2 = "#narrow/is/private";
    browser_history.go_to_location(hash1);
    assert.equal(location.hash, hash1);

    browser_history.update(hash2);
    assert.equal(location.hash, hash2);
    assert.equal(browser_history.old_hash(), hash1);

    const was_internal_change = browser_history.save_old_hash();
    assert(was_internal_change);
    assert.equal(browser_history.old_hash(), hash2);
});

test("update with same hash", () => {
    const hash = "#keyboard-shortcuts";

    browser_history.update(hash);
    assert.equal(location.hash, hash);
    browser_history.update(hash);
    assert.equal(location.hash, hash);
});

test("error for bad hashes", () => {
    const hash = "bogus";
    blueslip.expect("error", "programming error: prefix hashes with #: bogus");
    browser_history.update(hash);
});
