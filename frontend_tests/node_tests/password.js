"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

set_global("zxcvbn", zrequire("zxcvbn", "zxcvbn"));
zrequire("common");

run_test("basics", () => {
    let accepted;
    let password;
    let warning;

    const bar = (function () {
        const self = {};

        self.width = function (width) {
            self.w = width;
            return self;
        };

        self.removeClass = function (arg) {
            assert.equal(arg, "bar-success bar-danger");
            return self;
        };

        self.addClass = function (arg) {
            self.added_class = arg;
            return self;
        };

        return self;
    })();

    function password_field(min_length, min_guesses) {
        const self = {};

        self.data = function (field) {
            if (field === "minLength") {
                return min_length;
            } else if (field === "minGuesses") {
                return min_guesses;
            }
            throw new Error(`Unknown field ${field}`);
        };

        return self;
    }

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

    set_global("zxcvbn", undefined);
    password = "aaaaaaaa";
    accepted = common.password_quality(password, bar, password_field(6, 1e100));
    assert(accepted === undefined);
    warning = common.password_warning(password, password_field(6));
    assert(warning === undefined);
});
