"use strict";

const assert = require("node:assert/strict");

exports.CallbackData = class CallbackData {
    constructor(label) {
        this.label = label;
        this.obj = undefined;
    }

    set(obj) {
        assert.equal(typeof obj, "object", "Please pass in an object to set().");
        this.obj = obj;
    }

    get() {
        assert.ok(
            this.obj !== undefined,
            `
            We have no data yet for this callback:

            ${this.label}

            You need to invoke this only after some
            function has called the set() method.`,
        );
        return this.obj;
    }
};
