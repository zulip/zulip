// Silence jslint errors about the "console" global
/*global console: true */

var blueslip = (function () {

var exports = {};

var error_has_stack = Error().hasOwnProperty('stack');

var reported_errors = {};
function report_error(msg, opts) {
    opts = $.extend({}, {show_ui_msg: false}, opts);
    var stack;
    if (error_has_stack) {
        stack = Error().stack;
    } else {
        stack = 'No stacktrace available';
    }

    var key = msg + stack;
    if (reported_errors.hasOwnProperty(key)) {
        return;
    }

    $.ajax({
        type:     'POST',
        url:      '/json/report_error',
        dataType: 'json',
        data:     { message: msg, stacktrace: stack },
        timeout:  3*1000,
        success:  function () {
            reported_errors[key] = true;
            if (opts.show_ui_msg) {
                ui.report_message("Oops.  It seems something has gone wrong. " +
                                  "The error has been reported to the nice " +
                                  "folks at Humbug, but, in the mean time, " +
                                  "please try reloading the page.",
                                  $("#home-error"), "alert-error");
            }
        },
        error: function () {
            if (opts.show_ui_msg) {
                ui.report_message("Oops.  It seems something has gone wrong. " +
                                  "Please try reloading the page.",
                                  $("#home-error"), "alert-error");
            }
        }
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
        report_error(msg, {show_ui_msg: true});
    }

    throw new Error(msg);
};

return exports;
}());

/*global console: false */
