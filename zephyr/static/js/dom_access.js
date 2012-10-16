// We need to andSelf() because more often than not, the next item
// *is* a .message_row, so nextUntil returns an empty set (except for
// when it's in a bookend).
// (This could probably be further optimized by handling that case
// explicitly first, since it's also the common case.)
function get_next_visible(message_row) {
    if (message_row === undefined)
        return [];
    return message_row.nextUntil('.message_row').andSelf().next('.message_row');
}

function get_prev_visible(message_row) {
    if (message_row === undefined)
        return [];
    return message_row.prevUntil('.message_row').andSelf().prev('.message_row');
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
