"use strict";

const namespace = require("./namespace");
const zblueslip = require("./zblueslip");
const $ = require("./zjquery");
const zpage_billing_params = require("./zpage_billing_params");
const zpage_params = require("./zpage_params");

exports.run_test = (label, f, opts) => {
    test(label, async () => {
        const {sloppy_$} = opts || {};

        if (!sloppy_$ && $.clear_all_elements) {
            $.clear_all_elements();
        }
        zpage_billing_params.reset();
        zpage_params.reset();

        namespace._start_template_mocking();
        await namespace.with_overrides(async (helpers) => {
            await f({
                ...helpers,
                mock_template: namespace._mock_template,
            });
        });
        namespace._finish_template_mocking();
        // defensively reset blueslip after each test.
        zblueslip.reset();
    });
};
