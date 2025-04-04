"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {password_quality, password_warning} = zrequire("password_quality");

function password_field(min_length, max_length, min_guesses) {
    const self = {};

    self.attr = (name) => {
        switch (name) {
            case "data-min-length":
                return min_length;
            case "data-min-guesses":
                return min_guesses;
            case "data-max-length":
                return max_length;
            /* istanbul ignore next */
            default:
                throw new Error(`Unknown attribute ${name}`);
        }
    };

    return self;
}

run_test("basics w/progress bar", () => {
    let accepted;
    let password;
    let warning;

    const $bar = (function () {
        const $self = {};

        $self.width = (width) => {
            $self.w = width;
            return $self;
        };

        $self.removeClass = (arg) => {
            assert.equal(arg, "bar-success bar-danger");
            return $self;
        };

        $self.addClass = (arg) => {
            $self.added_class = arg;
            return $self;
        };

        return $self;
    })();

    password = "z!X4@S_&";
    accepted = password_quality(password, $bar, password_field(10, 80000));
    assert.ok(!accepted);
    assert.equal($bar.w, "39.7%");
    assert.equal($bar.added_class, "bar-danger");
    warning = password_warning(password, password_field(10));
    assert.equal(warning, "translated: Password should be at least 10 characters long.");

    password = "foo";
    accepted = password_quality(password, $bar, password_field(2, 200, 10));
    assert.ok(accepted);
    assert.equal($bar.w, "10.390277164940581%");
    assert.equal($bar.added_class, "bar-success");
    warning = password_warning(password, password_field(2));
    assert.equal(warning, "translated: Password is too weak.");

    password = "aaaaaaaa";
    accepted = password_quality(password, $bar, password_field(6, 1e100));
    assert.ok(!accepted);
    assert.equal($bar.added_class, "bar-danger");
    warning = password_warning(password, password_field(6));
    assert.equal(warning, 'Repeated characters like "aaa" are easy to guess.');

    // Test a password that's longer than the configured limit.
    password = "hfHeo34FksdBChjeruShJ@sidfgusd";
    accepted = password_quality(password, $bar, password_field(6, 20, 1e20));
    assert.ok(!accepted);
    assert.equal($bar.added_class, "bar-danger");
    warning = password_warning(password, password_field(6, 20, 1e20));
    assert.equal(warning, `translated: Maximum password length: 20 characters.`);
});
