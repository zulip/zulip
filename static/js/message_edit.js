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
        },
        error: function (xhr, error_type, xhn) {
            var message = util.xhr_error_message("Error saving edit", xhr);
            row.find(".message_edit_error").text(message).show();
        }
    });
    // The message will automatically get replaced when it arrives.
};

function handle_edit_keydown(e) {
    var row, code = e.keyCode || e.which;

    if (e.target.id === "message_edit_content" && code === 13 &&
        (e.metaKey || e.ctrlKey)) {
        row = $(".message_edit_content").filter(":focus").closest(".message_row");
        message_edit.save(row);
    }
}

function edit_message (row, raw_content) {
    var content_top = row.find('.message_content')[0]
        .getBoundingClientRect().top;

    var message = current_msg_list.get(rows.id(row));
    var edit_row = row.find(".message_edit");
    var form = $(templates.render('message_edit_form',
                                  {is_stream: message.is_stream,
                                   subject: message.subject,
                                   content: raw_content}));

    var edit_obj = {form: form, raw_content: raw_content};
    current_msg_list.show_edit_message(row, edit_obj);

    form.keydown(handle_edit_keydown);

    currently_editing_messages[message.id] = edit_obj;
    if (message.subject === compose.empty_subject_placeholder()) {
        edit_row.find(".message_edit_subject").focus();
    } else {
        edit_row.find(".message_edit_content").focus();
    }

    // Scroll to keep the message content in the same place
    var edit_top = edit_row.find('.message_edit_content')[0]
        .getBoundingClientRect().top;

    var scroll_by = edit_top - content_top + 5 /* border and padding */;
    edit_obj.scrolled_by = scroll_by;
    viewport.scrollTop(viewport.scrollTop() + scroll_by);
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
        var scroll_by = currently_editing_messages[message.id].scrolled_by;
        viewport.scrollTop(viewport.scrollTop() - scroll_by);
        delete currently_editing_messages[message.id];
        current_msg_list.hide_edit_message(row);
    }
};

exports.maybe_show_edit = function (row, id) {
    if (currently_editing_messages[id] !== undefined){
        current_msg_list.show_edit_message(row, currently_editing_messages[id]);
    }
};

$(document).on('narrow_deactivated.zulip', function (event) {
    _.each(currently_editing_messages, function (elem, idx) {
        if (current_msg_list.get(idx) !== undefined) {
            var row = current_msg_list.get_row(idx);
            current_msg_list.show_edit_message(row, elem);
        }
    });
});

return exports;
}());
