"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

window.location.hash = "#bogus";

const browser_history = zrequire("browser_history");
const {initialize_user_settings} = zrequire("user_settings");

const user_settings = {};
initialize_user_settings({user_settings});

function test(label, f) {
    run_test(label, (helpers) => {
        helpers.override(user_settings, "web_home_view", "recent");
        window.location.hash = "#bogus";
        browser_history.clear_for_testing();
        f(helpers);
    });
}

test("basics", () => {
    const hash1 = "#settings/profile";
    const hash2 = "#narrow/is/dm";
    browser_history.go_to_location(hash1);
    assert.equal(window.location.hash, hash1);

    browser_history.update(hash2);
    assert.equal(window.location.hash, hash2);
    assert.equal(browser_history.old_hash(), hash1);

    const was_internal_change = browser_history.save_old_hash();
    assert.ok(was_internal_change);
    assert.equal(browser_history.old_hash(), hash2);
});

test("update with same hash", () => {
    const hash = "#keyboard-shortcuts";

    browser_history.update(hash);
    assert.equal(window.location.hash, hash);
    browser_history.update(hash);
    assert.equal(window.location.hash, hash);
});

test("error for bad hashes", () => {
    const hash = "bogus";
    blueslip.expect("error", "programming error: prefix hashes with #");
    browser_history.update(hash);
});

test("update internal hash if required", () => {
    const hash = "#test/hash";
    browser_history.update_hash_internally_if_required(hash);
    assert.equal(window.location.hash, hash);

    // Calling again with the same hash should be a no-op.
    // If update() were called, it would log a blueslip.info
    // for the redundant hash, so verify no new info appeared.
    const info_count = blueslip.get_test_logs("info").length;
    browser_history.update_hash_internally_if_required(hash);
    assert.equal(blueslip.get_test_logs("info").length, info_count);
});

test("web-public view hash restore", () => {
    browser_history.update("#");
    assert.equal(window.location.hash, "");
    const new_hash = "#narrow/is/dm";
    browser_history.update(new_hash);
    assert.equal(window.location.hash, new_hash);
    browser_history.return_to_web_public_hash();
    assert.equal(window.location.hash, "#recent");
});
