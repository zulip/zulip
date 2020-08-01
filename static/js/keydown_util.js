"use strict";

/*
    See hotkey.js for handlers that are more app-wide.
*/

const keys = {
    13: "enter_key",
    37: "left_arrow",
    38: "up_arrow",
    39: "right_arrow",
    40: "down_arrow",
};

exports.handle = function (opts) {
    opts.elem.on("keydown", (e) => {
        const key = e.which || e.keyCode;

        if (e.altKey || e.ctrlKey || e.shiftKey) {
            return;
        }

        const key_name = keys[key];

        if (!key_name) {
            return;
        }

        if (!opts.handlers[key_name]) {
            return;
        }

        const handled = opts.handlers[key_name]();

        if (handled) {
            e.preventDefault();
            e.stopPropagation();
        }
    });
};

window.keydown_util = exports;
