"use strict";

// This is a general tour of how to write node tests that
// may also give you some quick insight on how the Zulip
// browser app is constructed.

// The statements below are pretty typical for most node
// tests. The reason we need these helpers will hopefully
// become clear as you keep reading.
const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

// We will use our special zrequire helper to import the
// Zulip code. We use zrequire instead of require,
// because it has some magic to clear state when we move
// on to the next test.
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const util = zrequire("util");

// Let's start with testing a function from util.ts.
//
// The most basic unit tests load up code, call functions,
// and assert truths:

assert.ok(!util.find_wildcard_mentions("boring text"));
assert.ok(util.find_wildcard_mentions("mention @**everyone**"));

// Let's test with people.js next.  We'll show this technique:
//  * get a false value
//  * change the data
//  * get a true value

const isaac = {
    email: "isaac@example.com",
    user_id: 30,
    full_name: "Isaac Newton",
};

// The `people`object is a very fundamental object in the
// Zulip app.  You can learn a lot more about it by reading
// the tests in people.test.js in the same directory as this file.

// Let's exercise the code and use assert to verify it works!
assert.ok(!people.is_known_user_id(isaac.user_id));
people.add_active_user(isaac);
assert.ok(people.is_known_user_id(isaac.user_id));

// Let's look at stream_data next, and we will start by putting
// some data at module scope. (You could also declare this inside
// the test, if you prefer.)

const denmark_stream = {
    color: "blue",
    name: "Denmark",
    stream_id: 101,
    subscribed: false,
};

// We introduce the run_test helper, which mostly just causes
// a line of output to go to the console. It does a little more than
// that, which we will see later.

run_test("verify stream_data persists stream color", () => {
    stream_data.clear_subscriptions();
    assert.equal(stream_data.get_sub_by_name("Denmark"), undefined);
    stream_data.add_sub(denmark_stream);
    const sub = stream_data.get_sub_by_name("Denmark");
    assert.equal(sub.color, "blue");
});
// See example2.test.js in this directory.
