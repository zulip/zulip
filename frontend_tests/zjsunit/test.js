"use strict";

const namespace = require("./namespace");
const zblueslip = require("./zblueslip");
const $ = require("./zjquery");
const zpage_params = require("./zpage_params");

let current_file_name;
let verbose = false;

exports.set_current_file_name = (value) => {
    current_file_name = value;
};

exports.set_verbose = (value) => {
    verbose = value;
};

exports.run_test = (label, f, opts) => {
    const {sloppy_$} = opts || {};

    if (verbose) {
        console.info("        test: " + label);
    }

    if (!sloppy_$ && $.clear_all_elements) {
        $.clear_all_elements();
    }
    zpage_params.reset();

    try {
        namespace._start_template_mocking();
        namespace.with_overrides((override) => {
            f({override, mock_template: namespace._mock_template});
        });
        namespace._finish_template_mocking();
    } catch (error) {
        console.info("-".repeat(50));
        console.info(`test failed: ${current_file_name} > ${label}`);
        console.info();
        throw error;
    }
    // defensively reset blueslip after each test.
    zblueslip.reset();
};
