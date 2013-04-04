// This must be included before the first call to $(document).ready
// in order to be able to report exceptions that occur during their
// execution.

// Silence jslint errors about the "console" global
/*global console: true */

var blueslip = (function () {

var exports = {};

var reported_errors = {};
var last_report_attempt = {};
function report_error(msg, stack, opts) {
    opts = $.extend({}, {show_ui_msg: false}, opts);

    if (stack === undefined) {
        stack = 'No stacktrace available';
    }

    var key = ':' + msg + stack;
    if (reported_errors.hasOwnProperty(key)
        || (last_report_attempt.hasOwnProperty(key)
            // Only try to report a given error once every 5 minutes
            && (Date.now() - last_report_attempt[key] <= 60 * 5 * 1000)))
    {
        return;
    }

    last_report_attempt[key] = Date.now();

    // TODO: If an exception gets thrown before we setup ajax calls
    // to include the CSRF token, our ajax call will fail.  The
    // elegant thing to do in that case is to either wait until that
    // setup is done or do it ourselves and then retry.
    $.ajax({
        type:     'POST',
        url:      '/json/report_error',
        dataType: 'json',
        data:     { message: msg,
                    stacktrace: stack,
                    ui_message: opts.show_ui_msg,
                    more_info: JSON.stringify(opts.more_info),
                    user_agent: window.navigator.userAgent},
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

function BlueslipError(msg, more_info) {
    var self = Error.call(this, msg);
    if (more_info !== undefined) {
        self.more_info = more_info;
    }
    return self;
}

BlueslipError.prototype = Error.prototype;

exports.wrap_function = function blueslip_wrap_function(func) {
    if (func.blueslip_wrapper !== undefined) {
        func.blueslip_wrapper_refcnt++;
        return func.blueslip_wrapper;
    }
    var new_func = function blueslip_wrapper() {
        if (page_params.debug_mode) {
            return func.apply(this, arguments);
        }

        try {
            return func.apply(this, arguments);
        } catch (ex) {
            // Treat exceptions like a call to fatal() if they
            // weren't generated from fatal()
            if (ex instanceof BlueslipError) {
                throw ex;
            }

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
    };
    func.blueslip_wrapper = new_func;
    func.blueslip_wrapper_refcnt = 1;
    return new_func;
};

// Catch all exceptions from jQuery event handlers, $(document).ready
// functions, and ajax success/failure continuations and funnel them
// through blueslip.
(function() {
    // This reference counting scheme can't break all the circular
    // references we create because users can remove jQuery event
    // handlers without referencing the particular handler they want
    // to remove.  We just hope this memory leak won't be too bad.
    function dec_wrapper_refcnt(func) {
        if (func.blueslip_wrapper_refcnt !== undefined) {
            func.blueslip_wrapper_refcnt--;
            if (func.blueslip_wrapper_refcnt === 0) {
                delete func.blueslip_wrapper;
                delete func.blueslip_wrapper_refcnt;
            }
        }
    }

    $.ajaxPrefilter(function (options) {
        $.each(['success', 'error', 'complete'], function (idx, cb_name) {
            if (options[cb_name] !== undefined) {
                options[cb_name] = exports.wrap_function(options[cb_name]);
            }
        });
    });

    if (document.addEventListener) {
        var orig_on = $.fn.on;
        var orig_off = $.fn.off;
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
            // that we have to replicate the code :(
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

            return orig_on.call(this, types, selector, data, exports.wrap_function(fn), one);
        };

        $.fn.off = function (types, selector, fn) {
            if (types && types.preventDefault && types.handleObj) {
                // (event)
                // We'll get called again through the recursive call in the original
                // $.fn.off
                return orig_off.call(this, types, selector, fn);
            }

            if (typeof types === "object" ) {
                // ( types-object [, selector] )
                // We'll get called again through the recursive call in the original
                // $.fn.off
                return orig_off.call(this, types, selector, fn);
            }

            // Only one handler, but we have to figure out which
            // argument it is.  The argument munging is taken from
            // jQuery, itself.
            if ( selector === false || typeof selector === "function" ) {
                // ( types [, fn] )
                fn = selector;
                selector = undefined;
            }
            if ( fn === false ) {
                fn = function () { return false; };
            }

            if (fn) {
                var wrapper = fn.blueslip_wrapper;
                if (wrapper !== undefined) {
                    dec_wrapper_refcnt(fn);
                    fn = wrapper;
                }
            }
            return orig_off.call(this, types, selector, fn);
        };

        $.fn.ready = function blueslip_jquery_ready_wrapper(func) {
            return orig_ready.call(this, exports.wrap_function(func));
        };
    }
}());

exports.log = function blueslip_log (msg, more_info) {
    console.log(msg);
    if (more_info !== undefined) {
        console.log("Additional information: ", more_info);
    }
};

exports.info = function blueslip_info (msg, more_info) {
    console.info(msg);
    if (more_info !== undefined) {
        console.info("Additional information: ", more_info);
    }
};

exports.warn = function blueslip_warn (msg, more_info) {
    console.warn(msg);
    if (page_params.debug_mode) {
        console.trace();
    }
    if (more_info !== undefined) {
        console.warn("Additional information: ", more_info);
    }
};

exports.error = function blueslip_error (msg, more_info) {
    if (page_params.debug_mode) {
        throw new BlueslipError(msg, more_info);
    } else {
        console.error(msg);
        if (more_info !== undefined) {
            console.error("Additional information: ", more_info);
        }
        report_error(msg, Error().stack, {more_info: more_info});
    }
};

exports.fatal = function blueslip_fatal (msg, more_info) {
    if (! page_params.debug_mode) {
        report_error(msg, Error().stack, {show_ui_msg: true,
                                          more_info: more_info});
    }

    throw new BlueslipError(msg, more_info);
};

return exports;
}());

/*global console: false */
