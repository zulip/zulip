var rows = (function () {

    var exports = {};

    // We don't need an andSelf() here because we already know
    // that our next element is *not* a message_row, so this
    // isn't going to end up empty unless we're at the bottom or top.
    exports.next_visible = function (message_row) {
        if (message_row === undefined)
            return $();
        var row = message_row.next('.message_row');
        if (row.length !== 0) {
            return row;
        }
        return message_row.nextUntil('.message_row').next('.message_row');
    };

    exports.prev_visible = function (message_row) {
        if (message_row === undefined)
            return $();
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
        return parseInt(message_row.attr('zid'), 10);
    };

    var valid_table_names = {
        zhome: true,
        zfilt: true
    };

    exports.get = function (message_id, table_name) {
        // Make sure message_id is just an int, because we build
        // a jQuery selector using it.
        message_id = parseInt(message_id, 10);
        if (isNaN(message_id))
            return $();

        // To avoid attacks and bizarre errors, we have a whitelist
        // of valid table names.
        if (! valid_table_names.hasOwnProperty(table_name))
            return $();

        return $('#' + table_name + message_id);
    };

    exports.get_table = function (table_name) {
        if (! valid_table_names.hasOwnProperty(table_name))
            return $();

        return $('#' + table_name);
    };

    return exports;

}());
