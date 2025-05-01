"use strict";

const assert = require("node:assert/strict");

exports.SideEffect = class SideEffect {
    constructor(label) {
        this.label = label;
        this.num_times_met = 0;
        this._allowed_to_happen = false;
    }

    has_happened() {
        assert.ok(
            this._allowed_to_happen,
            `
            The following side effect occurred BEFORE you
            expected it to happen.

                ${this.label}

            This would make the test confusing, since you
            want to verify that the side effect ONLY
            happens DURING the invocation of should_happen_during.

            This will help future developers understand
            the interactions that you intend.\n`,
        );

        this.num_times_met += 1;
    }

    should_happen_during(f) {
        // f should be a function with no parameters
        // and no return value
        this._allowed_to_happen = true;
        this.num_times_met = 0;
        f();
        assert.ok(
            this.num_times_met > 0,
            `

            The following side effect did not occur as expected:

                ${this.label}

            This means a call to something like side_effect.has_happened()
            was either never coded or was not called at the time you
            expected it to be called.\n`,
        );
        this._allowed_to_happen = false;
    }

    should_not_happen_during(f) {
        // f should be a function with no parameters
        // and no return value
        this.num_times_met = 0;
        f();
        assert.ok(
            this.num_times_met === 0,
            `

            The following side effect occurred unexpectedly:

                ${this.label}
            `,
        );
    }
};
