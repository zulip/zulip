"use strict";

const namespace = require("./namespace");

let current_file_name;
let verbose = false;

exports.set_current_file_name = (value) => {
    current_file_name = value;
};

exports.set_verbose = (value) => {
    verbose = value;
};

exports.run_test = (label, f) => {
    if (verbose) {
        console.info("        test: " + label);
    }
    try {
        namespace.with_overrides(f);
    } catch (error) {
        console.info("-".repeat(50));
        console.info(`test failed: ${current_file_name} > ${label}`);
        console.info();
        throw error;
    }
    // defensively reset blueslip after each test.
    blueslip.reset();
};
