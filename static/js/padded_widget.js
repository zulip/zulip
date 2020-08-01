"use strict";

exports.update_padding = function (opts) {
    const content = $(opts.content_sel);
    const padding = $(opts.padding_sel);
    const total_rows = opts.total_rows;
    const shown_rows = opts.shown_rows;
    const hidden_rows = total_rows - shown_rows;

    if (shown_rows === 0) {
        padding.height(0);
        return;
    }

    const ratio = hidden_rows / shown_rows;

    const content_height = content.height();
    const new_padding_height = ratio * content_height;

    padding.height(new_padding_height);
    padding.width(1);
};

window.padded_widget = exports;
