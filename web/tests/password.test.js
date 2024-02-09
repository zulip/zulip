"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const {password_quality, password_warning} = zrequire("password_quality");

function password_field(min_length, min_guesses, max_length) {
    const self = {};

    self.data = (field) => {
        switch (field) {
            case "minLength":
                return min_length;
            case "minGuesses":
                return min_guesses;
            case "maxLength":
                return max_length;
            /* istanbul ignore next */
            default:
                throw new Error(`Unknown field ${field}`);
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
    accepted = password_quality(password, $bar, password_field(10, 80000, 100));
    assert.ok(!accepted);
    assert.equal($bar.w, "39.7%");
    assert.equal($bar.added_class, "bar-danger");
    warning = password_warning(password, password_field(10));
    assert.equal(warning, "translated: Password should be at least 10 characters long");

    password = "foo";
    accepted = password_quality(password, $bar, password_field(2, 200, 100));
    assert.ok(accepted);
    assert.equal($bar.w, "10.390277164940581%");
    assert.equal($bar.added_class, "bar-success");
    warning = password_warning(password, password_field(2));
    assert.equal(warning, "translated: Password is too weak");

    password = "aaaaaaaa";
    accepted = password_quality(password, $bar, password_field(6, 1e100, 100));
    assert.ok(!accepted);
    assert.equal($bar.added_class, "bar-danger");
    warning = password_warning(password, password_field(6));
    assert.equal(warning, 'Repeated characters like "aaa" are easy to guess.');

    password = "a@3#B".repeat(21);
    accepted = password_quality(password, $bar, password_field(6, 1000, 100));
    assert.ok(!accepted);
    warning = password_warning(password, password(6));
    assert.equal(warning, "Password should be atmost 100 characters long");
});
