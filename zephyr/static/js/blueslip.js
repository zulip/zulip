// Silence jslint errors about the "console" global
/*global console: true */

var blueslip = (function () {

var exports = {};

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
    }
};

exports.fatal = function blueslip_fatal (msg) {
    throw new Error(msg);
};

return exports;
}());

/*global console: false */
