// Silence jslint errors about the "console" global
/*global console: true */

var blueslip = (function () {

var exports = {};

var error_has_stack = Error().hasOwnProperty('stack');

function report_error(msg) {
    var stack;
    if (error_has_stack) {
        stack = Error().stack;
    } else {
        stack = 'No stacktrace available';
    }

    $.ajax({
        type:     'POST',
        url:      '/json/report_error',
        dataType: 'json',
        data:     { message: msg, stacktrace: stack },
        timeout:  10*1000
    });
}

exports.log = function blueslip_log (msg) {
    console.log(msg);
};

exports.info = function blueslip_info (msg) {
    console.info(msg);
};

exports.warn = function blueslip_warn (msg) {
    console.warn(msg);
    if (debug_mode) {
        console.trace();
    }
};

exports.error = function blueslip_error (msg) {
    if (debug_mode) {
        throw new Error(msg);
    } else {
        console.error(msg);
        report_error(msg);
    }
};

exports.fatal = function blueslip_fatal (msg) {
    if (! debug_mode) {
        report_error(msg);
    }

    throw new Error(msg);
};

return exports;
}());

/*global console: false */
