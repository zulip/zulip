var rows = (function () {

var exports = {};

// We don't need an andSelf() here because we already know
// that our next element is *not* a message_row, so this
// isn't going to end up empty unless we're at the bottom or top.
exports.next_visible = function (message_row) {
    if (message_row === undefined || message_row.length === 0) {
        return $();
    }
    var row = message_row.next('.selectable_row');
    if (row.length !== 0) {
        return row;
    }
    var recipient_row = exports.get_message_recipient_row(message_row);
    var next_recipient_rows = $(recipient_row).nextAll('.recipient_row');
    if (next_recipient_rows.length === 0) {
        return $();
    }
    return $('.selectable_row:first', next_recipient_rows[0]);
};

exports.prev_visible = function (message_row) {
    if (message_row === undefined || message_row.length === 0) {
        return $();
    }
    var row = message_row.prev('.selectable_row');
    if (row.length !== 0) {
        return row;
    }
    var recipient_row = exports.get_message_recipient_row(message_row);
    var prev_recipient_rows = $(recipient_row).prevAll('.recipient_row');
    if (prev_recipient_rows.length === 0) {
        return $();
    }
    return $('.selectable_row:last', prev_recipient_rows[0]);
};

exports.first_visible = function () {
    return $('.focused_table .selectable_row:first');
};

exports.last_visible = function () {
    return $('.focused_table .selectable_row:last');
};

exports.id = function (message_row) {
    return parseFloat(message_row.attr('zid'));
};

var valid_table_names = {
    zhome: true,
    zfilt: true,
};

exports.get_table = function (table_name) {
    if (! valid_table_names.hasOwnProperty(table_name)) {
        return $();
    }

    return $('#' + table_name);
};

exports.get_message_id = function (elem) {
    // Gets the message_id for elem, where elem is a DOM
    // element inside a message.  This is typically used
    // in click handlers for things like the reaction button.
    var row = $(elem).closest(".message_row");
    var message_id = exports.id(row);
    return message_id;
};

exports.get_closest_group = function (element) {
    // This gets the closest message row to an element, whether it's
    // a recipient bar or message.  With our current markup,
    // this is the most reliable way to do it.
    return $(element).closest("div.recipient_row");
};

exports.first_message_in_group = function (message_group) {
    return $('div.message_row:first', message_group);
};

exports.get_message_recipient_row = function (message_row) {
    return $(message_row).parent('.recipient_row').expectOne();
};

exports.get_message_recipient_header = function (message_row) {
    return $(message_row).parent('.recipient_row').find('.message_header').expectOne();
};

exports.recipient_from_group = function (message_group) {
    return message_store.get(exports.id($(message_group).children('.message_row').first().expectOne()));
};

exports.id_for_recipient_row = function (recipient_row) {
    // A recipient row can be either a normal recipient row, or
    // the FRB, which is a fake recipient row. If it's a FRB, it has
    // a 'zid' property that stores the message id it is directly over
    var msg_row = exports.first_message_in_group(recipient_row);
    if (msg_row.length === 0) {
        // If we're narrowing from the FRB, take the msg id
        // directly from it
        return exports.id(recipient_row);
    }
    return exports.id(msg_row);
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = rows;
}
