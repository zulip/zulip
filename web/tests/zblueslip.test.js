"use strict";

const {strict: assert} = require("assert");

const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");

/*

This test module actually tests our test code, particularly zblueslip, and
it is intended to demonstrate how to use zblueslip (as well as, of course,
verify that it works as advertised).

What is zblueslip?

    The zblueslip test module behaves like blueslip at a very surface level,
    and it allows you to test code that uses actual blueslip and add some
    custom validation for checking that only particular errors and warnings are
    thrown by our test modules.

    The test runner automatically replaces `blueslip` with an instance
    of a zblueslip object.

The code we are testing lives here:

    https://github.com/zulip/zulip/blob/main/web/tests/lib/zblueslip.js

Read the following contents for an overview of how zblueslip works. Also take a
look at `people_errors.test.js` for actual usage of this module.
*/

run_test("basics", () => {
    // Let's create a sample piece of code to test:
    function throw_an_error() {
        blueslip.error("world");
    }

    // Since the error 'world' is not being expected, blueslip will
    // throw an error.
    assert.throws(throw_an_error);
    // zblueslip logs all the calls made to it, and they can be used in asserts like:

    // Now, let's add our error to the list of expected errors.
    blueslip.expect("error", "world", 2);
    // This time, blueslip will just log the error, which is
    // being verified by the assert call on the length of the log.
    // We can also check for which specific error was logged, but since
    // our sample space is just 1 expected error, we are sure that
    // only that error could have been logged, and others would raise
    // an error, aborting the test.
    throw_an_error();
    // The following check is redundant; blueslip.reset() already asserts that
    // we got the expected number of errors.
    assert.equal(blueslip.get_test_logs("error").length, 2);

    // Let's clear the array of valid errors as well as the log. Now, all errors
    // should be thrown directly by blueslip.
    blueslip.reset();
    assert.throws(throw_an_error);
    // This call to blueslip.reset() would complain.
    assert.throws(() => {
        blueslip.reset();
    });

    // Let's repeat the above procedure with warnings. Unlike errors,
    // warnings shouldn't stop the code execution, and thus, the
    // behaviour is slightly different.

    function throw_a_warning() {
        blueslip.warn("world");
    }

    assert.throws(throw_a_warning);
    // Again, we do not expect this particular warning so blueslip.reset should complain.
    assert.throws(() => {
        blueslip.reset();
    });

    // Let's reset blueslip regardless of errors. This is only for demonstration
    // purposes here; do not reset blueslip like this in actual tests.
    blueslip.reset(true);

    // Now, let's add our warning to the list of expected warnings.
    // This time, we shouldn't throw an error. However, to confirm that we
    // indeed had logged a warning, we can check the length of the warning logs
    blueslip.expect("warn", "world");
    throw_a_warning();
    blueslip.reset();

    // However, we detect when we have more or less of the expected errors/warnings.
    blueslip.expect("warn", "world");
    assert.throws(() => {
        blueslip.reset();
    });
    // Again, forcefully reset blueslip.
    blueslip.reset(true);
});
