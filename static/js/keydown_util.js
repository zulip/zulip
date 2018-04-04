var keydown_util = (function () {

var exports = {};

/*
    See hotkey.js for handlers that are more app-wide.
*/

var keys = {
    37: 'left_arrow',
    38: 'up_arrow',
    39: 'right_arrow',
    40: 'down_arrow',
};

exports.handle = function (opts) {
    opts.elem.keydown(function (e) {
        var key = e.which || e.keyCode;

        var key_name = keys[key];

        if (!key_name) {
            return;
        }

        if (!opts.handlers[key_name]) {
            return;
        }

        var handled = opts.handlers[key_name]();

        if (handled) {
            e.preventDefault();
        }
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = keydown_util;
}
