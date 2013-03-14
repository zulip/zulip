// This must be included before the first call to $(document).ready
// in order to be able to report exceptions that occur during their
// execution.

// Silence jslint errors about the "console" global
/*global console: true */

var blueslip = (function () {

var exports = {};

var reported_errors = {};
function report_error(msg, stack, opts) {
    opts = $.extend({}, {show_ui_msg: false}, opts);

    if (stack === undefined) {
        stack = 'No stacktrace available';
    }

    var key = msg + stack;
    if (reported_errors.hasOwnProperty(key)) {
        return;
    }

    // TODO: If an exception gets thrown before we setup ajax calls
    // to include the CSRF token, our ajax call will fail.  The
    // elegant thing to do in that case is to either wait until that
    // setup is done or do it ourselves and then retry.
    $.ajax({
        type:     'POST',
        url:      '/json/report_error',
        dataType: 'json',
        data:     { message: msg, stacktrace: stack },
        timeout:  3*1000,
        success:  function () {
            reported_errors[key] = true;
            if (opts.show_ui_msg) {
                // There are a few races here (and below in the error
                // callback):
                // 1) The ui module or something it requires might
                //    not have been compiled or initialized yet.
                // 2) The DOM might not be ready yet and so fetching
                //    the #home-error div might fail.

                // There's not much we can do about (1) and we can't
                // solve (2) by using $(document).ready() because the
                // callback never gets called (I think what's going
                // on here is if the exception was raised by a
                // function that was called as a result of the DOM
                // becoming ready then the internal state of jQuery
                // gets messed up and our callback never gets
                // invoked).  In any case, it will pretty clear that
                // something is wrong with the page and the user will
                // probably try to reload anyway.
                ui.report_message("Oops.  It seems something has gone wrong. " +
                                  "The error has been reported to the fine " +
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

function BlueslipError() {
    return Error.apply(this, arguments);
}

BlueslipError.prototype = Error.prototype;

// Catch all exceptions from jQuery event handlers, $(document).ready
// functions, and ajax success/failure continuations and funnel them
// through blueslip.
(function() {
    function wrap_callback(func) {
        var new_func = function blueslip_wrapper() {
            if (debug_mode) {
                return func.apply(this, arguments);
            } else {
                try {
                    return func.apply(this, arguments);
                } catch (ex) {
                    // Treat exceptions like a call to fatal()
                    var message = ex.message;
                    if (ex.hasOwnProperty('fileName')) {
                        message += " at " + ex.fileName;
                        if (ex.hasOwnProperty('lineNumber')) {
                            message += ":" + ex.lineNumber;
                        }
                    }
                    report_error(message, ex.stack, {show_ui_msg: true});
                    throw ex;
                }
            }
        };
        return new_func;
    }

    $.ajaxPrefilter(function (options) {
        $.each(['success', 'error', 'complete'], function (idx, cb_name) {
            if (options[cb_name] !== undefined) {
                options[cb_name] = wrap_callback(options[cb_name]);
            }
        });
    });

    if (document.addEventListener) {
        var orig_on = $.fn.on;
        var orig_ready = $.fn.ready;

        $.fn.on = function blueslip_jquery_on_wrapper(types, selector, data, fn, one) {
            if (typeof types === 'object') {
                // ( types-Object, selector, data)
                // We'll get called again from the recursive call in the original
                // $.fn.on
                return orig_on.call(this, types, selector, data, fn, one);
            }

            // Only one handler, but we have to figure out which
            // argument it is.  The argument munging is taken from
            // jQuery itself, so we tell jslint to ignore the style
            // issues that the jQuery code would raise.  It sucks
            // that we have to replicate the code :/
            /*jslint eqeq: true */
            if ( data == null && fn == null ) {
                // ( types, fn )
                fn = selector;
                data = selector = undefined;
            } else if ( fn == null ) {
                if ( typeof selector === "string" ) {
                // ( types, selector, fn )
                fn = data;
                data = undefined;
                } else {
                // ( types, data, fn )
                fn = data;
                data = selector;
                selector = undefined;
                }
            }
            if ( fn === false ) {
                fn = function () { return false; };
            } else if ( !fn ) {
                return this;
            }
            /*jslint eqeq: false */

            return orig_on.call(this, types, selector, data, wrap_callback(fn), one);
        };

        $.fn.ready = function blueslip_jquery_ready_wrapper(func) {
            return orig_ready.call(this, wrap_callback(func));
        };
    }
}());

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
        throw new BlueslipError(msg);
    } else {
        console.error(msg);
        report_error(msg, Error().stack);
    }
};

exports.fatal = function blueslip_fatal (msg) {
    if (! debug_mode) {
        report_error(msg, Error().stack, {show_ui_msg: true});
    }

    throw new BlueslipError(msg);
};

return exports;
}());

/*global console: false */
