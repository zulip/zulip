var rows = (function () {

var exports = {};

// We don't need an andSelf() here because we already know
// that our next element is *not* a message_row, so this
// isn't going to end up empty unless we're at the bottom or top.
exports.next_visible = function (message_row) {
    if (message_row === undefined) {
        return $();
    }
    var row = message_row.next('.selectable_row');
    if (row.length !== 0) {
        return row;
    }
    return message_row.nextUntil('.selectable_row').next('.selectable_row');
};

exports.prev_visible = function (message_row) {
    if (message_row === undefined) {
        return $();
    }
    var row = message_row.prev('.selectable_row');
    if (row.length !== 0) {
        return row;
    }
    return message_row.prevUntil('.selectable_row').prev('.selectable_row');
};

exports.first_visible = function () {
    return $('.focused_table .selectable_row:first');
};

exports.last_visible = function () {
    return $('.focused_table .selectable_row:last');
};

exports.id = function (message_row) {
    return parseInt(message_row.attr('zid'), 10);
};

var valid_table_names = {
    zhome: true,
    zfilt: true
};

exports.get_table = function (table_name) {
    if (! valid_table_names.hasOwnProperty(table_name)) {
        return $();
    }

    return $('#' + table_name);
};

exports.get_closest_row = function (element) {
    // This gets the closest message row to an element, whether it's
    // a summary bar, recipient bar, or message.  With our current markup,
    // this is the most reliable way to do it.
    return $(element).closest(".message_row");
};

return exports;

}());
