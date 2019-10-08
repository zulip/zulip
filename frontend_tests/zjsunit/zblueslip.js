var exports = {};

exports.make_zblueslip = function (opts) {

    var lib = {};

    // Apply defaults
    opts = Object.assign({
        // Silently swallow all debug, log and info calls.
        debug: false,
        log: false,
        info: false,
        // Check against expected error values for the following.
        warn: true,
        error: true,
        fatal: true,
    }, opts);

    // Store valid test data for options.
    lib.test_data = {};
    lib.test_logs = {};
    Object.keys(opts).forEach(name => {
        lib.test_data[name] = [];
        lib.test_logs[name] = [];
    });
    lib.set_test_data = (name, message) => {
        lib.test_data[name].push(message);
    };
    lib.clear_test_data = (name) => {
        if (!name) {
            // Clear all data
            Object.keys(opts).forEach(name => {
                lib.test_data[name] = [];
                lib.test_logs[name] = [];
            });
            return;
        }
        lib.test_data[name] = [];
        lib.test_logs[name] = [];
    };

    lib.get_test_logs = (name) => {
        return lib.test_logs[name];
    };

    lib.check_error = (isblueslip = false) => {
        return function (error) {
            if (isblueslip) {
                assert(error.blueslip, "Not a blueslip error.");
                return true;
            }
            // If an error was thrown by zblueslip, we know that that
            // error was not in the list of expeccted errors for the test.
            assert(!error.blueslip, "Error not in expected errors.");
            return true;
        };
    };

    // Create logging functions
    Object.keys(opts).forEach(name => {
        if (!opts[name]) {
            // should just log the message.
            lib[name] = function (message, more_info, stack) {
                lib.test_logs[name].push({message, more_info, stack});
            };
            return;
        }
        lib[name] = function (message, more_info, stack) {
            lib.test_logs[name].push({message, more_info, stack});
            const exact_match_fail = lib.test_data[name].indexOf(message) === -1;
            const string_match_fail = lib.test_data[name].indexOf(message.toString()) === -1;
            if (exact_match_fail && string_match_fail) {
                var error = Error(`Invalid ${name} message: "${message}".`);
                error.blueslip = true;
                throw error;
            }
        };
    });

    lib.exception_msg = function (ex) {
        return ex.message;
    };

    lib.wrap_function = (f) => {
        return (...args) => {
            return f.apply(this, args);
        };
    };

    return lib;
};

module.exports = exports;
