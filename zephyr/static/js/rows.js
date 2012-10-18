// This file doesn't have any local state or helper functions, so it has
// a simpler structure than the proper modules.

var rows = {
    // We don't need an andSelf() here because we already know
    // that our next element is *not* a message_row, so this
    // isn't going to end up empty unless we're at the bottom or top.
    next_visible: function (message_row) {
        if (message_row === undefined)
            return [];
        var row = message_row.next('.message_row');
        if (row.length !== 0) {
            return row;
        }
        return message_row.nextUntil('.message_row').next('.message_row');
    },

    prev_visible: function (message_row) {
        if (message_row === undefined)
            return [];
        var row = message_row.prev('.message_row');
        if (row.length !== 0) {
            return row;
        }
        return message_row.prevUntil('.message_row').prev('.message_row');
    },

    first_visible: function () {
        return $('.focused_table .message_row:first');
    },

    last_visible: function () {
        return $('.focused_table .message_row:last');
    },

    id: function (message_row) {
        return message_row.attr('zid');
    },

    get: function (message_id, table_name) {
        if (table_name === undefined)
            table_name = (narrow.active() ? 'zfilt' : 'zhome');
        return $('#' + table_name + message_id);
    }
};
