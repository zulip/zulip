"use strict";

const namespace = require("./namespace.cjs");
const zblueslip = require("./zblueslip.cjs");
const $ = require("./zjquery.cjs");
const zpage_billing_params = require("./zpage_billing_params.cjs");
const zpage_params = require("./zpage_params.cjs");

let current_file_name;
let verbose = false;

exports.set_current_file_name = (value) => {
    current_file_name = value;
};

exports.set_verbose = (value) => {
    verbose = value;
};

exports.noop = () => {};

exports.suite = [];

async function execute_test(label, f) {
    /* istanbul ignore if */
    if (verbose) {
        console.info("        test: " + label);
    }

    $.clear_all_elements();
    zpage_billing_params.reset();
    zpage_params.reset();

    try {
        namespace._start_template_mocking();
        await namespace.with_overrides(async (helpers) => {
            await f({
                ...helpers,
                mock_template: namespace._mock_template,
            });
        });
        namespace._finish_template_mocking();
    } catch (error) /* istanbul ignore next */ {
        console.info("-".repeat(50));
        console.info(`test failed: ${current_file_name} > ${label}`);
        console.info();
        throw error;
    }
    // defensively reset blueslip after each test.
    zblueslip.reset();
}

exports.run_test = (label, f, opts) => {
    exports.suite.push(() => execute_test(label, f, opts));
};
