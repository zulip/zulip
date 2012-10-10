function get_next_visible(message_row) {
    if (message_row === undefined)
        return [];
    return message_row.nextAll('.message_row:first');
}

function get_prev_visible(message_row) {
    if (message_row === undefined)
        return [];
    return message_row.prevAll('.message_row:first');
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
