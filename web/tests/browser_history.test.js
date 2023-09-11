"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {make_stub} = require("./lib/stub");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const {user_settings} = require("./lib/zpage_params");

window.location.hash = "#bogus";

const browser_history = zrequire("browser_history");

function test(label, f) {
    run_test(label, (...args) => {
        user_settings.default_view = "recent";
        window.location.hash = "#bogus";
        browser_history.clear_for_testing();
        f(...args);
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

test("update internal hash if required", ({override_rewire}) => {
    const hash = "#test/hash";
    const stub = make_stub();
    override_rewire(browser_history, "update", stub.f);
    browser_history.update_hash_internally_if_required(hash);
    assert.equal(stub.num_calls, 1);

    window.location.hash = "#test/hash";
    // update with same hash
    browser_history.update_hash_internally_if_required(hash);
    // but no update was made since the
    // hash was already updated.
    // Evident by no increase in number of
    // calls to stub.
    assert.equal(stub.num_calls, 1);
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
