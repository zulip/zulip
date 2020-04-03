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
        fatal: true,
    };
    const names = Array.from(Object.keys(opts));

    // Store valid test data for options.
    lib.test_data = {};
    lib.test_logs = {};
    lib.seen_messages = {};

    for (const name of names) {
        lib.test_data[name] = [];
        lib.test_logs[name] = [];
        lib.seen_messages[name] = new Set();
    }

    lib.expect = (name, message) => {
        lib.test_data[name].push(message);
    };

    lib.check_seen_messages = () => {
        for (const name of names) {
            for (const message of lib.test_data[name]) {
                if (!lib.seen_messages[name].has(message)) {
                    throw Error('Never saw: ' + message);
                }
            }
        }
    };

    lib.reset = () => {
        lib.check_seen_messages();

        for (const name of names) {
            lib.test_data[name] = [];
            lib.test_logs[name] = [];
            lib.seen_messages[name].clear();
        }
    };

    lib.get_test_logs = (name) => {
        return lib.test_logs[name];
    };

    // Create logging functions
    for (const name of names) {
        if (!opts[name]) {
            // should just log the message.
            lib[name] = function (message, more_info, stack) {
                lib.seen_messages[name].add(message);
                lib.test_logs[name].push({message, more_info, stack});
            };
            continue;
        }
        lib[name] = function (message, more_info, stack) {
            if (typeof message !== 'string') {
                // We may catch exceptions in blueslip, and if
                // so our stub should include that.
                if (message.toString().includes('exception')) {
                    message = message.toString();
                } else {
                    throw Error('message should be string: ' + message);
                }
            }
            lib.seen_messages[name].add(message);
            lib.test_logs[name].push({message, more_info, stack});
            const exact_match_fail = !lib.test_data[name].includes(message);
            if (exact_match_fail) {
                const error = Error(`Invalid ${name} message: "${message}".`);
                error.blueslip = true;
                throw error;
            }
        };
    }

    lib.exception_msg = function (ex) {
        return ex.message;
    };

    lib.start_timing = () => {
        return () => {};
    };

    return lib;
};
