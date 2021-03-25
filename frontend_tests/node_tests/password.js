"use strict";

const {strict: assert} = require("assert");

const {set_global, with_field, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

set_global("zxcvbn", require("zxcvbn"));

const common = zrequire("common");

function password_field(min_length, min_guesses) {
    const self = {};

    self.data = (field) => {
        if (field === "minLength") {
            return min_length;
        } else if (field === "minGuesses") {
            return min_guesses;
        }
        throw new Error(`Unknown field ${field}`);
    };

    return self;
}

run_test("basics w/progress bar", () => {
    let accepted;
    let password;
    let warning;

    const bar = (function () {
        const self = {};

        self.width = (width) => {
            self.w = width;
            return self;
        };

        self.removeClass = (arg) => {
            assert.equal(arg, "bar-success bar-danger");
            return self;
        };

        self.addClass = (arg) => {
            self.added_class = arg;
            return self;
        };

        return self;
    })();

    password = "z!X4@S_&";
    accepted = common.password_quality(password, bar, password_field(10, 80000));
    assert(!accepted);
    assert.equal(bar.w, "39.7%");
    assert.equal(bar.added_class, "bar-danger");
    warning = common.password_warning(password, password_field(10));
    assert.equal(warning, "translated: Password should be at least 10 characters long");

    password = "foo";
    accepted = common.password_quality(password, bar, password_field(2, 200));
    assert(accepted);
    assert.equal(bar.w, "10.390277164940581%");
    assert.equal(bar.added_class, "bar-success");
    warning = common.password_warning(password, password_field(2));
    assert.equal(warning, "translated: Password is too weak");

    password = "aaaaaaaa";
    accepted = common.password_quality(password, bar, password_field(6, 1e100));
    assert(!accepted);
    assert.equal(bar.added_class, "bar-danger");
    warning = common.password_warning(password, password_field(6));
    assert.equal(warning, 'Repeats like "aaa" are easy to guess');
});

run_test("zxcvbn undefined", () => {
    // According to common.js, we load zxcvbn.js asynchronously, so the
    // variable might not be set.  This just gets line coverage on the
    // defensive code.

    const password = "aaaaaaaa";
    const progress_bar = undefined;

    with_field(global, "zxcvbn", undefined, () => {
        const accepted = common.password_quality(password, progress_bar, password_field(6, 1e100));
        assert(accepted === undefined);
        const warning = common.password_warning(password, password_field(6));
        assert(warning === undefined);
    });
});
