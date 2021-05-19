"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {make_stub} = require("../zjsunit/stub");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");

const browser_history = zrequire("browser_history");

const location = set_global("location", {
    hash: "bogus",
});

function test(label, f) {
    run_test(label, ({override}) => {
        location.hash = "bogus";
        browser_history.clear_for_testing();
        f({override});
    });
}

test("basics", () => {
    const hash1 = "#settings/profile";
    const hash2 = "#narrow/is/private";
    browser_history.go_to_location(hash1);
    assert.equal(location.hash, hash1);

    browser_history.update(hash2);
    assert.equal(location.hash, hash2);
    assert.equal(browser_history.old_hash(), hash1);

    const was_internal_change = browser_history.save_old_hash();
    assert.ok(was_internal_change);
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

test("update internal hash if required", ({override}) => {
    const hash = "#test/hash";
    const stub = make_stub();
    override(browser_history, "update", stub.f);
    browser_history.update_hash_internally_if_required(hash);
    assert.equal(stub.num_calls, 1);

    location.hash = "#test/hash";
    // update with same hash
    browser_history.update_hash_internally_if_required(hash);
    // but no update was made since the
    // hash was already updated.
    // Evident by no increase in number of
    // calls to stub.
    assert.equal(stub.num_calls, 1);
});

test("web public view hash restore", () => {
    const allowed_hash = "#";
    browser_history.update(allowed_hash);
    assert.equal(location.hash, allowed_hash);
    const new_hash = "#narrow/is/private";
    browser_history.update(new_hash);
    assert.equal(location.hash, new_hash);
    browser_history.return_to_web_public_hash();
    assert.equal(location.hash, allowed_hash);
});
