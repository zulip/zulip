"use strict";

exports.make_zblueslip = function () {
    const lib = {};

    const opts = {
        // Silently swallow all debug, log and info calls.
        debug: false,
        log: false,
        info: false,
        // Check against expected error values for the following.
        warn: true,
        error: true,
    };
    const names = Array.from(Object.keys(opts));

    // For fatal messages, we should use assert.throws
    lib.fatal = (msg) => {
        throw new Error(msg);
    };

    // Store valid test data for options.
    lib.test_data = {};
    lib.test_logs = {};

    for (const name of names) {
        lib.test_data[name] = [];
        lib.test_logs[name] = [];
    }

    lib.expect = (name, message, count = 1) => {
        if (opts[name] === undefined) {
            throw new Error("unexpected arg for expect: " + name);
        }
        if (count <= 0 && Number.isInteger(count)) {
            throw new Error("expected count should be a positive integer");
        }
        const obj = {message, count, expected_count: count};
        lib.test_data[name].push(obj);
    };

    const check_seen_messages = () => {
        for (const name of names) {
            for (const obj of lib.test_logs[name]) {
                const message = obj.message;
                const i = lib.test_data[name].findIndex((x) => x.message === message);
                if (i === -1) {
                    // Only throw this for message types we want to explicitly track.
                    // For example, we do not want to throw here for debug messages.
                    if (opts[name]) {
                        throw new Error(`Unexpected '${name}' message: ${message}`);
                    }
                    continue;
                }
                lib.test_data[name][i].count -= 1;
            }

            for (const obj of lib.test_data[name]) {
                const message = obj.message;
                if (obj.count > 0) {
                    throw new Error(
                        `We did not see expected ${obj.expected_count} of '${name}': ${message}`,
                    );
                } else if (obj.count < 0) {
                    throw new Error(
                        `We saw ${obj.expected_count - obj.count} (expected ${
                            obj.expected_count
                        }) of '${name}': ${message}`,
                    );
                }
            }
        }
    };

    lib.reset = (skip_checks = false) => {
        if (!skip_checks) {
            check_seen_messages();
        }

        for (const name of names) {
            lib.test_data[name] = [];
            lib.test_logs[name] = [];
        }
    };

    lib.get_test_logs = (name) => lib.test_logs[name];

    // Create logging functions
    for (const name of names) {
        if (!opts[name]) {
            // should just log the message.
            lib[name] = function (message, more_info, stack) {
                lib.test_logs[name].push({message, more_info, stack});
            };
            continue;
        }
        lib[name] = function (message, more_info, stack) {
            if (typeof message !== "string") {
                // We may catch exceptions in blueslip, and if
                // so our stub should include that.
                if (message.toString().includes("exception")) {
                    message = message.toString();
                } else {
                    throw new Error("message should be string: " + message);
                }
            }
            lib.test_logs[name].push({message, more_info, stack});
            const matched_error_message = lib.test_data[name].find((x) => x.message === message);
            const exact_match_fail = !matched_error_message;
            if (exact_match_fail) {
                const error = new Error(`Invalid ${name} message: "${message}".`);
                error.blueslip = true;
                throw error;
            }
        };
    }

    lib.exception_msg = function (ex) {
        return ex.message;
    };

    lib.measure_time = (label, f) => f();

    lib.preview_node = (node) => "node:" + node;

    return lib;
};
