// We don't need an andSelf() here because we already know
// that our next element is *not* a message_row, so this
// isn't going to end up empty unless we're at the bottom or top.
function get_next_visible(message_row) {
    if (message_row === undefined)
        return [];
    var row = message_row.next('.message_row');
    if (row.length !== 0) {
        return row;
    }
    return message_row.nextUntil('.message_row').next('.message_row');
}

function get_prev_visible(message_row) {
    if (message_row === undefined)
        return [];
    var row = message_row.prev('.message_row');
    if (row.length !== 0) {
        return row;
    }
    return message_row.prevUntil('.message_row').prev('.message_row');
}

function get_first_visible() {
    return $('.focused_table .message_row:first');
}

function get_last_visible() {
    return $('.focused_table .message_row:last');
}

function get_id(message_row) {
    return message_row.attr('zid');
}

function get_message_row(message_id, table_name) {
    if (table_name === undefined)
        table_name = (narrowed ? 'zfilt' : 'zhome');
    return $('#' + table_name + message_id);
}
