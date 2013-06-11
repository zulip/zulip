var message_edit = (function () {
var exports = {};
var currently_editing_messages = {};

exports.save = function (row) {
    var msg_list = current_msg_list;
    var message = current_msg_list.get(rows.id(row));
    var new_subject = row.find(".message_edit_subject").val();
    var new_content = row.find(".message_edit_content").val();
    var request = {message_id: message.id};
    if (new_subject !== message.subject) {
        request.subject = new_subject;
    }
    if (new_content !== message.raw_content) {
        request.content = new_content;
    }
    if (request.subject === undefined &&
        request.content === undefined) {
        // If they didn't change anything, just cancel it.
        return message_edit.end(row);
    }
    $.ajax({
        type: 'POST',
        url: '/json/update_message',
        data: request,
        dataType: 'json',
        success: function (data) {
            if (msg_list === current_msg_list) {
                message_edit.end(row);
            }
        }
    });
    // The message will automatically get replaced when it arrives.
};

function edit_message (row, raw_content) {
    var message = current_msg_list.get(rows.id(row));
    var edit_row = row.find(".message_edit");
    var form = $(templates.render('message_edit_form',
                                  {is_stream: message.is_stream,
                                   subject: message.subject,
                                   content: raw_content}));

    var edit_obj = {form: form, raw_content: raw_content};
    current_msg_list.show_edit_message(row, edit_obj);

    currently_editing_messages[message.id] = edit_obj;
}

exports.start = function (row) {
    var message = current_msg_list.get(rows.id(row));
    var msg_list = current_msg_list;
    $.ajax({
        type: 'POST',
        url: '/json/fetch_raw_message',
        data: {message_id: message.id},
        dataType: 'json',
        success: function (data) {
            if (current_msg_list === msg_list) {
                message.raw_content = data.raw_content;
                edit_message(row, data.raw_content);
            }
        }
    });
};

exports.is_editing = function (id) {
    return currently_editing_messages[id] !== undefined;
};

exports.end = function (row) {
    var message = current_msg_list.get(rows.id(row));
    if (currently_editing_messages[message.id] !== undefined) {
        delete currently_editing_messages[message.id];
        current_msg_list.hide_edit_message(row);
    }
};

exports.maybe_show_edit = function(row, id) {
    if (currently_editing_messages[id] !== undefined){
        current_msg_list.show_edit_message(row, currently_editing_messages[id]);
    }
};

$(document).on('narrow_deactivated.zephyr', function (event) {
    $.each(currently_editing_messages, function(idx, elem) {
        if (current_msg_list.get(idx) !== undefined) {
            var row = rows.get(idx, current_msg_list.table_name);
            current_msg_list.show_edit_message(row, elem);
        }
    });
});

return exports;
}());
