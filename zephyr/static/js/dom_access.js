function get_next_visible(zephyr_row) {
    if (zephyr_row === undefined)
        return [];
    return zephyr_row.nextAll('.zephyr_row:first');
}

function get_prev_visible(zephyr_row) {
    if (zephyr_row === undefined)
        return [];
    return zephyr_row.prevAll('.zephyr_row:first');
}

function get_first_visible() {
    return $('.focused_table .zephyr_row:first');
}

function get_last_visible() {
    return $('.focused_table .zephyr_row:last');
}

function get_id(zephyr_row) {
    return zephyr_row.attr('zid');
}

function get_message_row(zephyr_id, table_name) {
    if (table_name === undefined)
        table_name = (narrowed ? 'zfilt' : 'zhome');
    return $('#' + table_name + zephyr_id);
}
