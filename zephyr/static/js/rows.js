var rows = (function () {

    var exports = {};

    // We don't need an andSelf() here because we already know
    // that our next element is *not* a message_row, so this
    // isn't going to end up empty unless we're at the bottom or top.
    exports.next_visible = function (message_row) {
        if (message_row === undefined)
            return [];
        var row = message_row.next('.message_row');
        if (row.length !== 0) {
            return row;
        }
        return message_row.nextUntil('.message_row').next('.message_row');
    };

    exports.prev_visible = function (message_row) {
        if (message_row === undefined)
            return [];
        var row = message_row.prev('.message_row');
        if (row.length !== 0) {
            return row;
        }
        return message_row.prevUntil('.message_row').prev('.message_row');
    };

    exports.first_visible = function () {
        return $('.focused_table .message_row:first');
    };

    exports.last_visible = function () {
        return $('.focused_table .message_row:last');
    };

    exports.id = function (message_row) {
        return message_row.attr('zid');
    };

    exports.get = function (message_id, table_name) {
        if (table_name === undefined)
            table_name = (narrow.active() ? 'zfilt' : 'zhome');
        return $('#' + table_name + message_id);
    };

    return exports;

}());
