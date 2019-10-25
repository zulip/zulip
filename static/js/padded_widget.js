exports.update_padding = function (opts) {
    var content = $(opts.content_sel);
    var padding = $(opts.padding_sel);
    var total_rows = opts.total_rows;
    var shown_rows = opts.shown_rows;
    var hidden_rows = total_rows - shown_rows;

    if (shown_rows === 0) {
        padding.height(0);
        return;
    }

    var ratio = hidden_rows / shown_rows;

    var content_height = content.height();
    var new_padding_height = ratio * content_height;

    padding.height(new_padding_height);
    padding.width(1);
};


window.padded_widget = exports;
